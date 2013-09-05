#!/usr/bin/env python
#
"""
    This file empdies the basic containers class.
    NetContainer will derive from that class, so will
    other contained products in the future.
    
    methods:
    
    
"""
import os
from rim import *
import subprocess
import xml.dom.minidom
import simplejson as json
from string import Template
from settings.handlers import ipinfo,dns,containers
from settings.command import *
import logging
from logging.handlers import *

croot="%s/containers" % Rim().dataDir

def isMountPoint(mntDir):
    mfile=open("/proc/mounts", "r")
    line=mfile.readline()
    while len(line) > 0:
        if line.split()[1][6:]==mntDir:
            mfile.close()
            return True
        line=mfile.readline()
    mfile.close()
    return False

def doMount(logger, options, mntDir):
    if isMountPoint(mntDir):
        return False
    else:
        ok, ret = runCmd(logger, "mount -n %s %s" % (options, mntDir))
        return ok
        
class Lxc():

    # cpu allocation type
    # share the parents cpu pool with others
    SCHED_SHARED    =   1
    # dedicate a number of CPUs to to each container 
    SCHED_DEDICATED =   2
    # use limit inforcement  (cpuLimit is a %)
    SCHED_LIMITED   =   3
    
    # states of a container
    STATE_NEW       = 1
    STATE_BUILT     = 2
    STATE_CREATED   = 3
    STATE_STARTED   = 4
    STATE_ERROR     = -1

    def __init__(self, name, index, version, ipBase, ipMask):
        self.rim=Rim()
        self.diskSpace=1024*1024
        self.memory=1024
        self.sched=self.SCHED_SHARED
        self.cpuLmit=0
        self.name="%s%d" % (name,index)
        self.index=index
        self.ipBase=ipBase
        self.ipMask=ipMask
        #
        # where we put the containers by default
        #
        self.croot=croot
        self.myroot="%s/%s" % (self.croot,self.name)
        #
        # by default we use current version
        #
        self.version=version
        self.node=self.rim.curNode()
        self.variant=self.rim.curVariant()
        self.syslog=logger(self.name).log
        #
        # initialise out current state
        self.state=self.getMyState()
    
    def isRunning(self):
        cmd="lxc-kill --name %s 1" % self.name
        return self.runCmd(cmd)
   
    def isCreated(self):
        cmd="lxc-ls 2>&1 | grep -w %s" % self.name
        return self.runCmd(cmd)
   
    def isBuilt(self):
        cmd="[ -f %s/go ]" % (self.myroot)
        return self.runCmd(cmd)
   
    def runCmd(self, cmd, exitOk=[0]):
        ok, ret = runCmd(self.syslog, cmd, exitOk)
        return ok

    def getMyState(self):
        if self.isRunning():
            return self.STATE_STARTED
        if self.isCreated():
            return self.STATE_CREATED
        if self.isBuilt():
            return self.STATE_BUILT
        return self.STATE_NEW
    
    # terminate all processes within the container
    def stop(self):
        self.runCmd("while lxc-kill -n %s 2>/dev/null; do sleep 1; done" % (self.name))
            
    # start init in the container
    def start(self):
        self.runCmd("lxc-start -d -n %s /sbin/init" % (self.name))
                    
    # create the container
    def create(self):
        self.runCmd("lxc-create -n %s -f %s/lxc.conf" % (self.name, self.myroot))

    # destroy the container
    def destroy(self):
        self.runCmd("lxc-destroy -n %s" % (self.name))
    
    # generate a stabel MAC address from the IP base address and our index
    def makeMac(self):
        ip=self.ipBase.split('.')
        return "00:FF:%02X:%02X:%02X:%02X" % (int(ip[0]), int(ip[1]), int(ip[2]), int(ip[3])+self.index)

    def makeIp(self):
        ip=self.ipBase.split('.')
        return "%d.%d.%d.%d" % (int(ip[0]), int(ip[1]), int(ip[2]), int(ip[3])+self.index)
    
    # convert a network mask string to a cidr bit count
    def maskBits(self):
        mask=0
        for field in self.ipMask.split("."):
            mask = (mask << 8) + int(field)
        bits=32
        while not mask & 0x1:
            bits = bits-1
            mask = mask >> 1
        return bits
        
    #
    # Mount a private copy of the version
    # We do this through aufs all the module mount points accept including the
    # rw cache as it is (but ro this time) and supplying a new rw cache on top of that.
    #
    # We can remount /soft as is.
    # We need a private data space which includes a private and shared section
    #
    def mountit(self):
        #
        # create the new rw cache from the native one
        #
        rwFs="%s/rwjail.fs" % self.myroot
        # find a free loop device
        stdout=[]
        runCmd(self.syslog, "losetup -f", out=stdout)
        device=stdout[0].split()[0]
        if not os.path.isfile(rwFs):
        # create the file using seek to end methodology
            cmd="dd if=/dev/zero bs=1 seek=%sk count=1 of=%s 2>/dev/null" % (self.diskSpace, rwFs)
            if not self.runCmd(cmd): return False
            cmd="losetup %s %s" % (device, rwFs)
            if not self.runCmd(cmd): return False
            cmd="mkfs -t ext3 %s 2>/dev/null 1>&2" % device
            if not self.runCmd(cmd): 
                self.runCmd("losetup -d %s" % device)
                return False
        else:
            cmd="losetup %s %s" % (device, rwFs)
            if not self.runCmd(cmd): return False
            cmd="fsck -y -t ext3 %s 2>/dev/null 1>&2 " % (device)
            if not self.runCmd(cmd, [ 0, 1, 2 ]): 
                # something really bad happened to that cache - re-create it
                cmd="mkfs -t ext3 %s 2>/dev/null 1>&2" % device
                if not self.runCmd(cmd): 
                    self.runCmd("losetup -d %s" % device)
                    return False
            
        # detach the loop device to that the mount/unmount can track it using -o loop
        # there may be a lag between outstanding i/o and unataching 
        cmd="losetup -d %s || (sleep 2 && losetup -d %s )" % (device, device)
        self.runCmd(cmd)
        self.runCmd("mkdir -p %s/rwjail" % self.myroot)
        doMount(self.syslog, "-o loop %s" % rwFs, "%s/rwjail" %  self.myroot)
        #
        # create a list of all the mounts for this node and version
        # Use the bom.xml for that version
        #
        bomFile="%s/%s/bom.xml" % (self.rim.softDir, self.version)
        xmlNode=xml.dom.minidom.parse(bomFile)
        #
        # scan through all of the module entries
        #
        modules={}
        for modNode in xmlNode.getElementsByTagName('module'):
            for amfNode in modNode.getElementsByTagName('amf'):
                nodeName=amfNode.getAttribute('name')
                if nodeName == self.node:
                    modName=modNode.getAttribute('name')
                    modLevel=modNode.getAttribute('level')
                    modules[modName]=int(modLevel)
        #
        # proceed with the construction of the mount options
        # Note: aufs - use +wh on ro rwcache original so taht it will respect the whiteouts
        #       present there.
        #
        mounts="%s/rwjail=rw:%s/rwjail=ro+wh" % (self.myroot, croot)
        for level in reversed(range(16)):
            for modName in modules:
                if modules[modName] == level:
                    mounts="%s:%s=ro" % (mounts, "%s/%s/%s" % (self.rim.softDir, self.version, modName))
        #
        # ready for the mount proper
        #
        try:
            os.mkdir("%s/root" % self.myroot)
        except:
            pass
        if doMount(self.syslog, "-t aufs -o rw,udba=none,dirs=%s aufs" % mounts, "%s/root" % self.myroot):
            self.runCmd("rm -f %s/root/__curlevel__" % self.myroot)
        # create a flag file that tells the container about it being a container
        os.system("touch %s/root/%s" % (self.myroot, containers.FLAG_FILE))
        # run all registered lxcsetup actions from bom.xml.sh
        self.runCmd("runAction lxcsetup %s/root %s" % (self.myroot, self.name))
        #
        # change the IP address to the BASE+index
        #
        cmd="getSystemInfo %s %s %s" % (ipinfo.myId, dns.myId, containers.myId)
        child = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        cfg=child.communicate()[0]
        cfg=json.loads(cfg)
        ipinfo.setIp(cfg[ipinfo.myId], self.makeIp())
        dns.setName(cfg[dns.myId], self.name)
        containers.setEnabled(cfg[containers.myId], False)
        # ajust run level of container to the one prior to level 8
        prevLevel=containers.getPrevLevel(cfg[containers.myId])
        cmd='chroot %s/root setSystemInfo' % (self.myroot)
        child = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        child.stdin.write(json.dumps(cfg, sort_keys=True, indent=4))
        child.stdin.close()
        #
        # ajust run level of container to the one prior to level 8
        #
        prevLevel=containers.getPrevLevel(cfg[containers.myId])
        self.runCmd("sed -i -e 's/id:8:initdefault:/id:%s:initdefault:/g' %s/root/etc/inittab" % (prevLevel, self.myroot))
        #
        # tell the container it is one
        os.system("touch %s/root/%s" % (self.myroot, containers.FLAG_FILE))
        return True
        
    #
    # reverse of the mount process
    # 
    def unmountit(self):
        #
        # create a list of all the mounts for this node and version
        # Use the bom.xml for that version
        #
        bomFile="%s/%s/bom.xml" % (self.rim.softDir, self.version)
        xmlNode=xml.dom.minidom.parse(bomFile)
        #
        # scan through all of the module entries
        #
        modules=[]
        modules.append("root/pivot/soft")
        modules.append("root/pivot/data")
        modules.append("root/proc")
        modules.append("root")
        modules.append("rwjail")
        for module in modules:
            cmd="umount %s/%s" % (self.myroot, module)
            self.runCmd(cmd)
        
        return True

    # build everything we need outside of the lxc domain for our container
    # config , mounts etc...
    def build(self):
        #
        # get to work.
        # We need to create our container root directory and create a lxc.conf file
        # with the proper settings for us.
        #
        # The lxc module includes a lxc.conf and fstab template for use here.
        #
        # Variables of the templates:
        # CONTAINER_ROOT    - our runtime root
        # CONTAINER_NAME    - our name
        # CONTAINER_MAC     - need to assign a mac to each (should be stable)
        # CONTAINER_FATAB   - the fatab for us
        # CONTAINER_IPV4    - Ip address and mask bits ex: 192.168.1.222/24        
        #
        # ROOT
        env={}
        env['CONTAINER_ROOT']="%s/root" % self.myroot
        env['CONTAINER_CONSOLE']="%s/console.out" % self.myroot
        env['CONTAINER_NAME']=self.name
        env['CONTAINER_MAC']=self.makeMac()
        fstab="%s/fstab" % self.myroot
        env['CONTAINER_FSTAB']=fstab
        env['CONTAINER_IPV4']="%s/%s" % (self.makeIp(), self.maskBits())

        #
        # make the directory itself
        #
        try:
            os.mkdir(self.croot, 0755)
        except:
            pass
        try:
            os.mkdir(self.myroot, 0755)
        except:
            pass
        #
        # run the templates
        #
        # lxc.conf
        try:
            s=open("/etc/lxc.conf.tpl", "r").read()
            s=Template(s).substitute(env)
            open("%s/lxc.conf" % self.myroot, "w").write(s)
        except:
            self.state=self.STATE_ERROR
            return False
        #
        # fstab
        #
        try:
            s=open("/etc/fstab.tpl", "r").read()
            s=Template(s).substitute(env)
            open("%s/fstab" % self.myroot, "w").write(s)
        except:
            self.state=self.STATE_ERROR
            return False
        #
        # mount a private copy of the specified version
        #
        if not self.mountit():
            self.state=self.STATE_ERROR
            return False
        #
        # we should be good to go
        open("%s/go" % self.myroot, "w")
        self.state=self.STATE_BUILT
        return True

    def remove(self):
        self.unmountit()
        cmd="umount %s/rwjail" % (self.croot)
        self.runCmd(cmd)
        cmd="rm -f %s/go" % (self.myroot)
        self.runCmd(cmd)

