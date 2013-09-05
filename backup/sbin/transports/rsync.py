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
    return "ssh"

class SshTransport(transport.Transport):

    def __init__(self, cfg, logger):
        transport.Transport.__init__(self, cfg)
        cmd="rsync -av --no-links ${OPTIONS} -R --rsh=ssh --stats --link-dest=${REFDIR} ${INCLUDE} ${EXCLUDE} ${SOURCEDIR} %s@%s:%s/${DSTDIR} || exit 1" % (
                self.getName(),
                self.getHost(),
                self.getDir()
            )
        self.outCmd=Template(cmd)
        cmd="rsync -rltpDO -R --progress --rsh=ssh ${OPTIONS} --rsync-path='cd %s/${DSTDIR} && rsync' --stats %s@%s:. . || exit 1" % (
                self.getDir(),
                self.getName(),
                self.getHost()
            )
        self.inCmd=Template(cmd)
        self.log=rim.logger("rsync").log
        self.logErr=logger
        
    def typeName(self): return myTname
    
    # prefix to add to a set of commands dealing with the backups
    def cmdPrefix(self):
        return "ssh %s@%s" % (self.getName(),self.getHost())
    
    #
    # Validate
    #
    def validate(self, pw=""):

        error=""
        rsaKey="/root/.ssh/id_rsa"
        hostFile="/root/.ssh/known_hosts"

        ssh=paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        self.log("validation in progress pw='%s'" % pw)

        #
        # setup the keys
        # ssh-keygen [-q] [-b bits] -t type [-N new_passphrase] [-C comment] [-f output_keyfile]
        try:
            open(rsaKey, "r")
            fd=open("%s.pub" % rsaKey, "r")
            mykey = paramiko.RSAKey.from_private_key_file(rsaKey)
        except:
            cmd="ssh-keygen -q  -t rsa -N '' -f %s" % rsaKey
            ok, code = rim.runCmd(self.log, cmd)
            try:
                fd=open("%s.pub" % rsaKey, "r")
                mykey = paramiko.RSAKey.from_private_key_file(rsaKey)
            except:
                ssh.close()
                return "Key generation failed : %d" % code

        #make sure host key file exists
        open(hostFile, "w").close()
        #let paramiko know where it is so that AutoAffPolicy can add any new keys to it
        ssh.load_host_keys(hostFile)

        try:
            self.log("Connecting")
            ssh.connect(self.getHost(),username=self.getName(), pkey=mykey)
            self.log("Connected")
        except paramiko.AuthenticationException:
            if len(pw) == 0:
                if sys.stdin.isatty():
                    while True:
                        try:
                            pw=getpass.getpass(prompt="Please enter password:");
                        except:
                            sys.exit(1)
                        if len(pw) == 0:
                            s="password is required"
                            self.log(s)
                            ssh.close()
                            return s
                        try:
                            ssh.connect(self.getHost(),username=self.getName(),password=pw)
                            break
                        except Exception as detail:
                            self.log("password is required")
                            return "Connection failed : %s" % detail
                else:
                    ssh.close()
                    s="Authentication failed"
                    self.log(s)
                    return s

            else:
                try:
                    ssh.connect(self.getHost(),username=self.getName(),password=pw)
                except paramiko.AuthenticationException:
                    ssh.close()
                    s="Invalid password or username was supplied"
                    self.log(s)
                    return s
                except Exception as detail:
                    ssh.close()
                    s="Could not connect to '%s@%s' : %s" % (self.getName(),self.getHost(),detail)
                    self.log(s)
                    return s
            #
            # add our public key to the user's authorized hosts list
            #
            cmd='mkdir -p -m 0700 .ssh && cat >> .ssh/authorized_keys && chmod 600 .ssh/authorized_keys'
            self.log("ssh '%s'" % cmd)
            (stdin, stdout, stderr) = ssh.exec_command(cmd)
            stdin.write(fd.read())
            stdin.close()
            stdout.close()
            stderr.close()
            ssh.close()
            try:
                ssh.connect(self.getHost(),username=self.getName(), pkey=mykey)
            except Exception as detail:
                s="Password less access failed - %s" % (detail)
                self.log(s)
                return s
        except Exception as detail:
            s="connection to '%s@%s' : %s" % (self.getName(),self.getHost(),detail)
            self.log(s)
            return s

        ssh.close()        
        return error
    
        
    #
    # default command modificator
    #
    def mkCmd(self, cmd):
        return "%s 'cd %s && %s'" % (self.cmdPrefix(), self.getDir(), cmd)
    #
    # send a single file
    #
    def sendFile(self, src, dst):
        cmd="scp %s %s@%s:%s/%s" % (
            src, 
            self.getName(),
            self.getHost(),
            self.getDir(),
            dst
        )
        ok, code = rim.runCmd(self.log, cmd)
        return ok

    #
    # setup 
    #
    def setup(self):
        # we only need to make sure the root directory for the backups has been created.
        cmd="%s mkdir -p %s" % (self.cmdPrefix(),self.getDir())
        self.log(cmd)
        ok, code = rim.runCmd(self.log, cmd)
        return ok
    #
    # run
    #
    
    #
    # setdown
    #
    def setdown(self):
        return True

# hook for dynamic loading
def get(cfg, logger):
    return SshTransport(cfg, logger)
        
