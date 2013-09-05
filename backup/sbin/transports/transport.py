#
# transport base class
#
import paramiko
import sys
import getpass
import subprocess
import rim
from string import Template

# where the backup process keep running status of % done
pctFile="/var/run/backups.pct"
# Any final errors from the backup process is recorded here
errorFile="/var/run/backups.err"
# File that contains the last status of the backups (starting, estimating, running, success, failed)
statusFile="/var/run/backups.status"
# where to send output of rsync commands
logFile="/var/log/backups.log"

#
# Each transport will format a command to run for an rsync of a specific directory.
# A set of template variables are defined to cover all variabls of each such command.
# They are:
#
# ${INCLUDE}   -- Replaced with --include clause (if specified)
# ${EXCLUDE}   -- Replaced with --exclude clause (if specified)
# ${REFDIR}    -- Replaced with the reference directory to use 
# ${SOURCEDIR} -- Replaced by destination directory (name includes current data/time)
# ${DSTDIR}    -- Replaced with the directory 

SERVER_ATTR="Server"
USERNAME_ATTR="UserName"
PASSWORD_ATTR="Password"
DIR_ATTR="Directory"

class Transport():

    SERVER_ATTR="Server"
    USERNAME_ATTR="UserName"
    PASSWORD_ATTR="Password"
    DIR_ATTR="Directory"
    
    # gets
    def getHost(self):
        return self.cfg[SERVER_ATTR]
    def getName(self):
        return self.cfg[USERNAME_ATTR]
    def getDir(self):
        return self.cfg[DIR_ATTR]
                
    # INIT
    def __init__(self, cfg):
        self.cfg=cfg
        self.mntpt="/pivot/data/%s" % self.typeName()()
        self.log=rim.logger('transport[%s]' % self.typeName()()).log
        self.outCmd=Template("cd %s/${DSTDIR} && rsync -av --no-links ${OPTIONS} -R --stats --link-dest=${REFDIR} ${INCLUDE} ${EXCLUDE} ${SOURCEDIR} . || exit 1" % (
                self.mntpt
            ))
        self.inCmd=Template("rsync -rltpD -R --progress ${OPTIONS} --rsync-path='cd %s/${DSTDIR} && rsync' --stats . || exit 1" % (
                self.mntpt
            ))
        self.label="RimBackups"
    #
    # Validate
    #
    def validate(self, pw="", rec=False):
        raise "Missing validate hook in transport!"
    
    #
    # default command modificator
    #
    def mkCmd(self, cmd):
        return "cd %s && %s" % ( self.mntpt, cmd)
    
    #
    # check and return a mount for out moujnt point
    #
    def isMounted(self):
        for line in open("/proc/mounts", "r").read().split("\n"):
            fields=line.split()
            if len(fields) > 1 and fields[1] == self.mntpt:
                return line
        return ""
        
    #
    # extract an option from a mount line
    #
    def getOption(self, line, option):
        options=line.split(",")
        for opt in options:
            assign=opt.split("=")
            if assign[0] == option:
                if len(assign) > 1:
                    return assign[1]
                else:
                    return assign[0]
        return ""
        
    #
    # setup
    #
    def setup(self, pw="", rec=False):
        raise "Missing validate hook in transport!"
    
   
    #
    # setdown
    #
    def validate(self, pw="", rec=False):
        raise "Missing validate hook in transport!"
