#
#
# base class for iso handlers
#
#
import os
import sys
import time
import rim
from settings.handlers import ipinfo

dataDir=rim.Rim().dataDir
isoDir="/pivot%s/isos" % dataDir

class iso():

    def __init__(self):
        self.refs=0
        self.name=self.mntpt.split('/')[-1]
        self.log=rim.logger("iso[%s]" % self.name).log
        # get our own ip config
        ipjson=ipinfo.get()
        ipcfg=rim.jsonToObject(ipjson)
        self.myIp=ipcfg.IPAddress
        
    def defaultPath(self):
        self.log("Pure virtual method 'defaultPath' not defined !")
        sys.exit(1)

    def kernelPath(self, name):
        self.log("Pure virtual method 'kernelPath' not defined !")
        sys.exit(1)

    def initrdPath(self, name):
        self.log("Pure virtual method 'initrdPath' not defined !")
        sys.exit(1)

    #
    # check and return a mount for out moujnt point
    #
    def isMounted(self):
        for line in open("/proc/mounts", "r").read().split("\n"):
            fields=line.split()
            if len(fields) > 1 and fields[1] == "%s" % (self.mntpt):
                self.log("Iso '%s is mounted" % self.name)
                return True
        self.log("Iso '%s not mounted" % self.name)
        return False
        
    #
    # check if the current mounted iso is older then current one in the iso pool
    #
    def isNewerArrived(self):
        path="%s/%s.iso" % (isoDir, self.name)
        if os.path.exists("%s.mounted" % path):
            t1=os.path.getctime(path)
            t2=os.path.getctime("%s.mounted" % path)
            self.log("t1=%d" % t1)
            self.log("t2=%d" % t2)
            if t2 >= t1:
                return False
        self.log("Newer version of ISO '%s' detected" % self.name)
        return True
    #
    # start using a iso image for boot -- mount it.
    #
    def use(self):
        self.log("Use self.name '%s'" % (self.name))
        #
        # check if we have it mounted
        #
        if not self.isMounted() or self.isNewerArrived():
        
            # get rid of old version mount and export
            if self.isMounted():
                rim.runCmd(self.log, "exportfs -u '*:%s'" % (self.mntpt))
                rim.runCmd(self.log, "umount %s" % (self.mntpt))
                
            # make a copy 
            rim.runCmd(self.log, "cp %s/%s.iso %s/%s.iso.mounted" % (isoDir, self.name, isoDir, self.name))
                
            rim.runCmd(self.log, "mkdir -p %s" % (self.mntpt))
            ok, code = rim.runCmd(self.log, "mount -o loop %s/%s.iso.mounted %s" % (isoDir, self.name, self.mntpt))
            if not ok:
                self.log("Failed to mount iso")
                return False
                
            # export it
            ok, code = rim.runCmd(self.log, "exportfs '*:%s'" % (self.mntpt))
            if not ok:
                self.log("Failed to export iso")
                rim.runCmd(self.log, "umount %s" % (self.mntpt))
                rim.runCmd(self.log, "rm -f %s/%s.iso.mounted" % (isoDir, self.name))
                return False
        return True
    #
    # unmount and clenaup
    #   
    def release(self):
        self.log("Release self.name '%s'" % (self.name))
        ok, code = rim.runCmd(self.log, "umount %s" % (self.mntpt))
        if not ok:
            self.log("warning : Failed to unmount iso")
