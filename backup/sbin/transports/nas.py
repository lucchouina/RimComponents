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
from transports import transport
from string import Template

def myTname():
    return "nas"

class CifsTransport(transport.Transport):

    def __init__(self, cfg, errLogger):
        transport.Transport.__init__(self, cfg)
        # use base class out and in Cmds.
        self.log=rim.logger("nas").log
        self.logErr=errLogger
        self.outCmd=Template("cd %s/${DSTDIR} && rsync -av --no-links ${OPTIONS} -R --stats --link-dest=${REFDIR} ${INCLUDE} ${EXCLUDE} ${SOURCEDIR} . || exit 1" % (
                self.mntpt
            ))
        self.inCmd=Template("rsync -rltpDO --progress ${OPTIONS} --stats %s/${DSTDIR}/. / || exit 1" % (
                self.mntpt
            ))

    def typeName(self): return myTname
    
    #
    # override the base handler to include some checks
    def getDir(self):
        d=self.cfg[transport.DIR_ATTR]
        # substitute all '\' for '/'
        d=d.replace('\\','/')
        # make sur ethere are no dup '/'
        d.replace('//','/')
        # check that we have a leading /
        if d[0:1] != '/':
            d='/'+d
        return d
    
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
    # setup 
    #
    def setup(self, errors=None):
    
        # check if the mount is already active
        # with the same parameters
        # We do not want to keep mounting/unmounting every minute
        mnt=self.isMounted()
        if len(mnt):
            fields=mnt.split()
            # check host and dir
            src="//%s%s" % (self.getHost(), self.getDir())
            if src != fields[0]:
                self.log("Dir changed '%s' versus '%s'" % (src,fields[0]))
                self.unMount()
            else:
                username=self.getOption(mnt, 'username')
                if len(username):
                    if username != self.getName():
                        self.log("Name changed '%s' versus '%s'" % (username,self.getName()))
                        self.unMount()
                    else:
                        # already mounted
                        return True

        mnt=self.isMounted()
        if not len(mnt):
            if errors==None: errors=[]
            cmd="mkdir -p %s" % self.mntpt
            rim.runCmd(self.log, cmd, errors=errors)
            cmd="mount -n -t cifs -o user='%s',password=%s //%s'%s' %s" % (
                self.getName(),
                self.cfg[transport.PASSWORD_ATTR],
                self.getHost(),
                self.getDir(),
                self.mntpt
            )
            ok, code = rim.runCmd(self.log, cmd, errors=errors)
            if not ok :
                if len(errors) > 0:
                    msg=errors[0]
                else:
                    msg="unknown error"
                self.logErr("Nas mount failure [%s]" % msg)
            return ok
        else:
            self.log("Mounted")
        
    def setdown(self):
        return True
    
    
    def unMount(self):
        if len(self.isMounted()):
            cmd="umount %s" % self.mntpt
            ok, code = rim.runCmd(self.log, cmd)
            return ok
        else:
            return True

# hook for dynamic loading
def get(cfg, errLogger):
    return CifsTransport(cfg, errLogger)
        

