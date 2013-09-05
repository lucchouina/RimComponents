#!/usr/bin/env python
#

#
# handler for rsync/ssh transport
#
import paramiko
import sys
import os
import getpass
import subprocess
import rim
import glob
import stat
from transports import transport
from string import Template

def myTname():
    return "iscsi"
    
class iscsiSession():

    def __init__(self, dev): 
        # read link of the /sys/block device
        link=os.readlink("/sys/block/%s" % dev)
        self.dst="/".join([ '/sys' ] + link.split("/")[1:])
        self.root="/".join([ '/sys' ] + link.split("/")[1:5])
        self.address=self.readFile("connection*/iscsi_connection/connection*/address")
        self.port=self.readFile("connection*/iscsi_connection/connection*/port")
        self.username=self.readFile("iscsi_session/session*/username")
        self.password=self.readFile("iscsi_session/session*/password")
        self.targetname=self.readFile("iscsi_session/session*/targetname")
        self.state=self.readFile("iscsi_session/session*/state")
        self.major, self.minor =  os.readlink("%s/bdi" % self.dst).split('/')[-1].split(':')

    def readFile(self, path):
        cmd="cat %s/%s" % (self.root, path)
        child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        ret = child.wait()
        stdout, stderr = child.communicate()
        return stdout.split('\n')[0]

class IscsiTransport(transport.Transport):

    def __init__(self, cfg, logger):
        transport.Transport.__init__(self, cfg)
        # use base class out and in Cmds.
        self.log=rim.logger("iscsi").log
        self.logErr=logger
        self.outCmd=Template("cd %s/${DSTDIR} && rsync -av --no-links ${OPTIONS} -R --stats --link-dest=${REFDIR} ${INCLUDE} ${EXCLUDE} ${SOURCEDIR} . || exit 1" % (
                self.mntpt
            ))
        self.inCmd=Template("rsync -rltpDO --progress ${OPTIONS} --stats %s/${DSTDIR}/. / || exit 1" % (
                self.mntpt
            ))
        
        
    def typeName(self): return myTname
    
    #
    # Validate
    #
    def validate(self, pw=""):

        errors=[]
        if not self.setup(errors=errors):
            return errors[0]
        self.setdown()
        return ""
        
    #
    # send a single file
    #
    def sendFile(self, src, dst):
    
        if not self.setup():
            return False
        
        cmd="cp %s %s/%s" % (
            src,
            self.mntpt,
            dst
        )
        ok, code = rim.runCmd(self.log, cmd)
        
        self.setdown()
        return ok
        
    #
    # scan for existing active sessions
    #
    def getDevices(self):
        stdout=[]
        ok, code = rim.runCmd(self.log, "iscsiadm -m session -P3 | grep 'Attached scsi disk'", out=stdout)
        if not ok: return []
        newpaths=[]
        for line in stdout:
            fields=line.split()
            if len(fields):
                newpaths.append(fields[3])
        return newpaths
    #
    # format and label a new device
    #
    def formatAndLabel(self, devName):
        stderr=[]
        ok, code = rim.runCmd(self.log, "mkfs -F -t ext3 /dev/%s" % devName, errors=stderr)
        if not ok: 
            self.logErr("Failed to create filesystem '%s'" % stderr[0])
            return False
        ok, code = rim.runCmd(self.log, "e2label /dev/%s %s" % (devName, self.label), errors=stderr)
        if not ok: 
            self.logErr("Failed to label filesystem '%s'" % stderr[0])
            return False
        return True
        
            
    #
    # setup 
    #
    def setup(self, errors=None):
    
        #
        # something is mounted already ?
        mnt=self.isMounted()
        if len(mnt):
        
            rim.runCmd(self.log, "mkdir -p %s" % self.mntpt)

            hostFields=self.getHost().split(":")
            host=hostFields[0]
            if len(hostFields) > 1:
                port=hostFields[1]
            else:
                port="3260"
            
            # validate the parameters of the iscsi sesssion
            self.session=iscsiSession(mnt.split()[0].split("/")[-1])
            if self.session.address != host or self.session.port != port or self.session.targetname != self.getDir():
                self.log("Found new iscsi parameters - remounting")
                self.log("addr %s - %s " % (self.session.address, host))
                self.log("port %s - %s " % (self.session.port, port))
                self.log("dir  %s - %s " % (self.session.targetname, self.getDir()))
                self.unMount()
            else:
                #
                # all good - keep it asis
                return True
        #
        # clear to log in and mount
        mnt=self.isMounted()
        if not len(mnt):

            # start the iscsi deamon (in case it is not already started)    
            ok, code = rim.runCmd(self.log, "/etc/init.d/open-iscsi status", errors=errors)
            if not ok:
                ok, code = rim.runCmd(self.log, "/etc/init.d/open-iscsi start", errors=errors)
                if not ok:
                    self.logErr("Failed to start iscsi deamon")
                    return False
            
            # make a list of existing iscsi device so we can find which one we created
            devPaths=self.getDevices()
            if len(devPaths) == 0:
                #
                # discover can take more then a minute if the packet if lost in route
                self.logErr("Discovery in progress...", "discovery")
                rim.runCmd(self.log, "iscsiadm -m discovery -t st -p %s" % self.getHost(), errors=errors)

                #
                # log in (no CHAP support for now)
                cmd = "iscsiadm -m node --target=%s -p %s --login" % (self.getDir(), self.getHost())
                ok, code = rim.runCmd(self.log, cmd, errors=errors)
                if not ok:
                    self.logErr("Failed to login to iscsi session")
                    return False

                # Get the new device path
                devPaths=self.getDevices()
                if len(devPaths) != 1:
                    self.logErr("iScsi session device not found %s"% devPaths)

            # Try to mount the device
            devName=devPaths[0]
            self.log("found device '%s'" % devName)

            # get a handle on that new session
            self.session=iscsiSession(devName)
            if not self.session:
                self.logErr("Failed to find session for device %s" % devName)
                self.setdown()
                return False

            # make sure deive exists in /dev
            if not os.path.exists("/dev/%s" % devName):
                try:
                    os.mknod("/dev/%s" % devName, stat.S_IFBLK+0644, os.makedev(int(self.session.major), int(self.session.minor)))
                except:
                    self.logErr("Failed to create device /dev/%s" % devName)
                    raise
                    self.setdown()
                    return False

            # check if we see our volume label here
            out=[]
            ok, code = rim.runCmd(self.log, "e2label /dev/%s" % devName, out=out)
            if not ok or out[0] != self.label:
                self.logErr("e2label failed - new device - curlabel '%s'" % out[0])
                if not self.formatAndLabel(devName):
                    self.setdown()
                    return False

            cmd="mount /dev/%s %s" % (devName, self.mntpt)
            ok, code = rim.runCmd(self.log, cmd)
            if not ok:
                self.log("warning : mount failed - fsck'ing")
                cmd="fsck -y -t ext3 %s 2>/dev/null 1>&2 " % (device)
                # fsck will exit with various non-zero values 
                if not rim.runCmd(self.log, cmd, [ 0, 1, 2 ]):
                    self.logErr("Failed to access partition")
                    self.setdown()
                    return False
                cmd="mount /dev/%s %s" % (devName, self.mntpt)
                ok, code = rim.runCmd(self.log, cmd)
                if not ok:
                    self.log("fatal : mount failed after fsck'ing")
                    return False
        # all good
        return True
    
    #
    # unmount
    #
    def unMount(self):
        if len(self.isMounted()):
            cmd="umount %s" % self.mntpt
            ok, code = rim.runCmd(self.log, cmd)
            if not ok : return False
        if self.session and self.session.state == "LOGED_IN":
            ok, code = rim.runCmd(self.log, "iscsiadm -m node -U all")
            self.log("Warning: failed to log out of current session")
        ok, code = rim.runCmd(self.log, "/etc/init.d/open-iscsi stop")
        if not ok:
            self.log("Failed to stop iscsi deamon")
        return True
    #
    # setdown
    #
    def setdown(self):
        return True

# hook for dynamic loading
def get(cfg, logger):
    return IscsiTransport(cfg, logger)
        

