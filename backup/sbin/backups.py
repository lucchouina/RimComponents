###########################################################################
#
#            Backup management class
#
###########################################################################
import os
import re
import sys
import time
import fcntl
import glob
import imp
import subprocess
import datetime
import simplejson as json
import rim

# where we record the pid of the owner of the lock file
pidFile="/var/run/backups.pid"
lockFile="/tmp/lockfile"
errorFile="/var/run/backups.err"
# File that contains the last status of the backups (starting, estimating, running, success, failed)
statusFile="/var/run/backups.status"
# where the backup process keep running status of % done
pctFile="/var/run/backups.pct"

# where the backup files form the components are kept
confDir="/etc/backups"

# ownership records are kept in this file at the top of each specified directory
recFile=".ownership"

myId="Backups"
ENABLED_ATTR="Enabled"
RECOVER_ATTR="Recover"
STATUS_ATTR="Status"
PROGRESS_ATTR="Progress"
ERROR_ATTR="Msg"
COMMAND_ATTR="Command"
PASSWORD_ATTR="Password"

recId="Recovery"
REC_LIST_ATTR="List"
REC_ENTRY_DATETIME_ATTR="Time"
REC_PREFIX_ATTR="Prefix"

class Backup():

    def __init__(self, configFile="/etc/backups.conf"):
        self.configFile=configFile;
        self.readCfg();
        self.transport=self.getTransport()
        # take a spapshot of the date/time here
        now = datetime.datetime.now()
        self.timesuffix="%4d_%02d_%02d-%02d.%02d.%02d" % (
            now.year,
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second
        )
        self.dbglevel=9
        self.log=rim.logger("Backup").log
                
    def dbg(self, level, msg):
        if self.dbglevel >= level:
            self.log(msg)
   
    def log_multi(self, m):
        for s in m:
            self.log(s)
 
    def logErr(self, s, status="error"):
        self.log("[error] %s" %s)
        open(errorFile, "w").write(s)
        self.write_status(status)
        
    def write_status(self, status):
        open(statusFile, "w").write(status)
        self.log("Status changed to %s" % status)
        self.cfg[STATUS_ATTR]=status
    
    def getTransport(self):
        for infile in sorted(glob.glob('%s/transports/*.py' % sys.path[0])):
            fname = os.path.basename(infile)[:-3]
            mod=imp.load_source(fname, infile) 
            if hasattr(mod, "myTname") and self.cfg['Type'] == mod.myTname():
                return mod.get(self.cfg, self.logErr)
        return None

    #
    # read the configuration into a jason struct
    #
    def readCfg(self):
        self.cfg=json.load(open(self.configFile));
        self.transport=self.getTransport()
        self.cfg[COMMAND_ATTR]=""
        # fill in the readonly variables
        #
        try:
            self.cfg[STATUS_ATTR]=open(statusFile, "r").readline()
        except:
            self.cfg[STATUS_ATTR]='inactive'

        if self.cfg[STATUS_ATTR] == "saving" or self.cfg[STATUS_ATTR] == "recovering":
           try:
               self.cfg[PROGRESS_ATTR]=open(pctFile, "r").readline()
           except:
               self.cfg[PROGRESS_ATTR]=""
        else:
            self.cfg[PROGRESS_ATTR]=""
        try:
            self.cfg[ERROR_ATTR]=open(errorFile, "r").readline()
        except:
            self.cfg[ERROR_ATTR]=""

    # So scripts can check if backup are enabled
    #
    def isEnabled(self):
        return self.cfg[ENABLED_ATTR];
    
    def doRecover(self):
        return self.cfg[RECOVER_ATTR];
    
    def setRecover(self, state):
        prev=self.cfg[RECOVER_ATTR]
        self.cfg[RECOVER_ATTR]=state;
        self.setCfg(None)
        return prev
    
    def setRunCfg(self, cfg):
        self.cfg=cfg
        self.transport=self.getTransport()

    def writeCfg(self, cfg):
        json.dump(cfg, open(self.configFile, "w"), sort_keys=True, indent=4);
    #
    # write and set new configuration
    #
    def setCfg(self, cfg):
        if cfg == None : cfg=self.cfg
        self.writeCfg(cfg)
        self.setRunCfg(cfg)
    #
    # 2 hooks used by the cfg handler
    #
    def startcmd(self):
        return "run-backups"
    def stopcmd(self):
        return "stop-backups"
    def recovercmd(self):
        return "run-recover latest"
    #
    # return the configuration 
    #
    def getCfg(self):
        return self.cfg;
    # gets
    def getHost(self):
        return self.cfg['Server']
    def getName(self):
        return self.cfg['UserName']
    def getStatus(self):
        return self.cfg[STATUS_ATTR]
    
    #
    # Get the % progress on an active backup
    #
    def getProgress(self):
        child = subprocess.Popen("(cat %s | grep to-check | tail -1) 2>/dev/null" % logFile, stdout=subprocess.PIPE, shell=True)
        output= child.communicate()
        if len(output[0]) :
            counts= output[0].split()[-1].split("=")[-1].split(")")[0].split("/")
            return ((int(counts[1])-int(counts[0]))*100)/int(counts[1])
        else:
            return 0
    #
    # Get the list of remote backups. This is essentialy a list of directories ordered by name
    # The name being a dat-time (incl. minutes) Backup_YYYYMMDD.HHMMSS
    # The lastest backup is first
    #
    def getBackups(self, prefix='Backup'):
        cmd=self.transport.mkCmd('/bin/ls -d %s_* 2>/dev/null' % prefix)
        self.log(cmd)
        child = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        backups=child.communicate()
        if len(backups) :
            return  backups[0].split("\n")
            
        else:
            return [ "" ]
            
    #
    # get the timestamp of the latest backup , if any
    #
    def getLatestTstamp(self):
        matches=self.getBackups('Latest')
        if len(matches) > 0:
            return matches[0][7:]
        else:
            return None
    #
    # figure out how much free disk space is available on the target
    #
    def getFreeSpace(self):
        cmd=self.transport.mkCmd("df -Pk . | tail -1")
        self.log(cmd)
        child = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        results = child.communicate()[0].split()
        if len(results) >= 4:
            return int(results[3])
        else:
            return 0
     
    #
    # delete the oldest backup on the target
    #
    def deleteOldest(self):
        dirs=self.getBackups()
        self.log_multi(dirs)
        if len(dirs) > 2:
            oldest=dirs[0]
            cmd=self.transport.mkCmd("rm -rf %s" % (oldest))
            self.log(cmd)
            child = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            child.wait()
            newOldest=self.getBackups()[0]
            self.log("new=%s oldest=%s" % ( newOldest, oldest))
            if newOldest == oldest:
                # something did not work - make sure we abort
                return False
            return True
        else:
            return False
        
    #
    # Get the full size of a full dry-run
    #
    def getFullSize(self):
        cmds, dirs=self.getCmds("_Backup_%s" % self.timesuffix, options="--dry-run")
        total=0
        files=0
        for cmd in cmds:
            self.log(cmd)
            child = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            results = child.communicate()
            (thisSize, theseFiles) = self.getThisSizeAndFiles(results[0])
            total += thisSize;
            files += theseFiles;
        return total, files
    #
    # Get the size in bytes of a single rsync
    #
    def getThisSizeAndFiles(self, output):
        p=re.compile('Total transferred file size:')
        m=p.search(output)
        if m :
            size=int(output[m.span()[1]:].split()[0])
        else:
            size=0
        p=re.compile('Number of files:')
        m=p.search(output)
        if m :
            files=int(output[m.span()[1]:].split()[0])
        else:
            files=0
        self.log( "size, file = %d, %d" % (size, files))
        return size, files
    #
    # get a list of directories from the configuration files
    #
    def getDirList(self):

        includes=[]
        excludes=[]
        
        # start by reading in all of the backup files
        listing = os.listdir(confDir)
        dirList=[]
        for filename in listing:
            fd=open("%s/%s" % (confDir,filename), "r")
            linei=fd.readline()
            while len(linei) > 0:
                # skip empty lines
                line=linei
                linei=fd.readline()
                fields=line.split()
                if len(fields) == 0:
                   continue;
                # skip comments
                if fields[0][0]=="#":
                    continue
                dir=fields[0]
                #
                # turn directories that are symb link into absolute path names
                #
                child = subprocess.Popen("cd %s && /bin/pwd" % dir, stdout=subprocess.PIPE, shell=True)
                dir=child.stdout.readline().strip('\n')
                recurse=True
                exclude=[]
                include=[]
                if len(fields) > 1:
                    if fields[1] == "true":
                        recurse=True
                    elif fields[1] == "false":
                        recurse=False
                    else:
                        self.log("Invalid value for recursion flag. %s. expected true or false." % fields[1])
                        sys.exit(1)
                    if len(fields) > 2:
                        if fields[2] != '-':
                            include=fields[2].split(",")
                        if len(fields) > 3:
                            if fields[3] != '-':
                                exclude=fields[3].split(",")
                dirList.append([ dir, recurse, include, exclude ])
        return dirList
    #
    # build a command line for purpose of backup or dry-run
    #
    def getCmds(self, newdir, options=""):
        dirList=self.getDirList()
        #
        # Now create the final command list
        #
        cmds=[]
        for dirEntry in dirList:
            cmd= self.transport.outCmd.safe_substitute({
                "OPTIONS"   : options,
                "INCLUDE"   : "".join(["--include '%s' " % x for x in dirEntry[2]]),
                "EXCLUDE"   : "".join(["--exclude '%s' " % x for x in dirEntry[3]]),
                "SOURCEDIR" : dirEntry[0],
                "DSTDIR"    : newdir,
                "REFDIR"    : "../Latest_%s" % self.getLatestTstamp()
            })
            cmds.append(cmd)
        cmds.append("exit 0")
        return cmds, dirList;

    #
    # lock/unlock using flock file
    #
    def lockit(self, wait=0):
        self.lockfd=open(lockFile, "w")
        try: os.chmod(lockFile, 0666)
        except: pass
        try:
            fcntl.fcntl(self.lockfd, fcntl.F_SETFD, fcntl.fcntl(self.lockfd, fcntl.F_GETFD) | fcntl.FD_CLOEXEC)
        except Exception, s:
            self.dbg(2, "warning: Failed to set CLOEXEC on lockfile - '%s'" % s)
        start=int(time.time())
        said=False
        self.log("Acquiring lock")
        while True:
            try:
                fcntl.flock(self.lockfd, fcntl.LOCK_EX+fcntl.LOCK_NB)
                break
            except:
                if not said:
                    self.log("Failed - retrying for %d seconds" % wait)
                said=True
                try:
                    pidstr=open(pidFile, "r").read()
                    if len(pidstr):
                        try:
                            self.pid=int(pidstr)
                        except:
                            self.pid=-1
                except:
                    self.pid=-1
                if self.pid == -1:
                    self.log("Warning - No pid file found when lock was held!")
                    # unlink that lock file and proceed
                    os.unlink(lockFile)
                else:
                    now=int(time.time())
                    if now-start >= wait:
                        self.log("Failed to lock after %d seconds, owner id %d" % (wait, self.pid))
                        self.lockfd.close()
                        return False
                    time.sleep(1)
        self.dbg(1, "Lock acquired - my pid %d" % os.getpid())
        open(pidFile, "w").write(str(os.getpid()))
        try: os.chmod(pidFile, 0666)
        except: pass
        self.pid=os.getpid()
        return True
        
    # unlock
    def unlockit(self):
        try:
            self.dbg(1, "Unlocking from pid %d" % os.getpid())
            pid=int(open(pidFile, "r").read())
            self.dbg(1, "Owner is %d" % pid)
            if pid == os.getpid():
                fcntl.flock(self.lockfd, fcntl.LOCK_UN)
                self.lockfd.close()
                self.dbg(1, "Removing pid file %s" % pidFile)
                os.remove(pidFile)
                self.dbg(1, "Removed.")
            else:
                self.log("Unmatched pids %s versus %d" % (os.getpid(), pid))
        except:
            pass

    def status(self):
        #
        # try to open a live backup. If it works, there's nothing going on.
        #
        if self.lockit() :
            status="Inactive"
            progress="0"
            try:
                error=open(self.transport.errorFile, "r").read()
            except:
                error="Success"
            self.unlockit()
        else:
            status="Active"
            progress=self.getProcess();
            error=""
        
        return [ status, progress, error ]
        
    def validate(self, pw="", rec=False):
        # no validation (and setup) when diabled.
        # validate when recovery is required.
        # use case  is that the user down not enable backups, enters password and requires recovery.
        #
        if not self.isEnabled() and not rec:
            return "";
            
        return self.transport.validate(pw)
    #
    # start a backup
    #
    def start(self, forced=False):
        returnCode=True
        #
        # if a recovery request is pending, bail out
        #
        if self.doRecover():
            return False

        # We assume the lock is already held by our parent process
            
        # check if backups are enabled
        if not self.cfg[ENABLED_ATTR]:
            return False
        #
        # Check that connection works
        #
        msg=self.validate()
        if len(msg):
            self.logErr(msg)
            return False
        #
        if not self.transport.setup():
            self.logErr("Failed to setup transport")
            return False
        #
        # make sure we have a backups directory created
        #
        self.logErr("Starting system backup", "starting")
        cmd=self.transport.mkCmd("mkdir -p _Backup_%s" %  self.timesuffix)
        rim.runCmd(self.log, cmd)

        #
        # get the full size of this backup first
        #
        self.logErr("Estimating backup size", "estimating")
        (size, allFiles)=self.getFullSize()
        # size in Kbytes and add 10% for safety
        size /= 1024
        size += (size*10)/100
        free=self.getFreeSpace()
        if allFiles == 0:
            open(pctFile, "w").write("100")
        self.log("free %d size %d" % (free, size))
        while free < size:
            if not self.deleteOldest():
                break;
            free=self.getFreeSpace()
        self.logErr("Backing up system", "saving")
        if free < size:
            # not enough space to perform the backup
            self.logErr("Not enough space on backup server. Need %d kbytes (available is %d)." % (size, free))
        else:
            # of to start the backup
            cmds, dirs=self.getCmds("_Backup_%s" % self.timesuffix, options="--progress")
            exitCode=1
            p1=re.compile('to-check=')
            p2=re.compile('Number of files:')
            doneFiles=0
            ppct=-1
            # 
            # Because the transport can lead to remapping of ownership and because some transports, like cifs/nas
            # will not support symblinks (Windows Samba server with no Unix extention support), we create a file that will
            # keep track of the ownership and links.
            # This file will be executed immediately after a restore 
            #
            self.log("Saving perms and links")
            for dir in dirs:
                cmd="(cd %s && find . -printf 'chown %%u:%%g %%p\\n' -type l -printf 'ln -s %%l %%p\\n' > %s)" % (dir[0], recFile)
                ok, retCode=rim.runCmd(self.log, cmd)
                if not ok:
                    self.logErr("'%s' failed with exit code %d" % (cmd, retCode))
                    returnCode=False
                    break
            if returnCode:
                cmd=self.transport.mkCmd("mkdir -p _Backup_%s" %  self.timesuffix)
                returnCode, code = rim.runCmd(self.log, cmd)
            if returnCode:
                for cmd in cmds:
                    self.log(cmd)
                    child = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
                    line=child.stdout.readline()
                    theseFiles=0
                    while len(line):
                        m=p1.search(line)
                        if m:
                            toCheck=int(line[m.span()[1]:].split('/')[0])
                            totalToCheck=int(line[m.span()[1]:].split('/')[1].split(')')[0])
                            theseFiles=totalToCheck-toCheck
                        else:
                            m=p2.search(line)
                            if m:
                                theseFiles=int(line[m.span()[1]+1:])
                        if allFiles > 0:                  
                            pct=((doneFiles+theseFiles)*100/allFiles)
                            open(pctFile, "w").write("%d" % pct)
                            if pct != ppct:
                                self.log("%d%%" % pct)
                                ppct=pct
                        line=child.stdout.readline()
                    exitCode=child.wait()
                    if exitCode != 0:
                        returnCode=False
                        self.logErr("rsync failed with error code %d" % (exitCode))
                        break
                    doneFiles += theseFiles
                if exitCode == 0:
                    latestTstamp=self.getLatestTstamp()
                    if latestTstamp:
                        # good to go - rename to a valid backup directory
                        cmd=self.transport.mkCmd("mv Latest_%s Backup_%s" % (
                            latestTstamp,
                            latestTstamp
                        ))
                        ok, code = rim.runCmd(self.log, cmd)
                    else: ok=True
                    returnCode=ok
                    if returnCode:
                        # good to go - move Latest to Backup
                        cmd=self.transport.mkCmd("mv _Backup_%s Latest_%s" % (
                            self.timesuffix,
                            self.timesuffix
                        ))
                        ok, code = rim.runCmd(self.log, cmd)
                        returnCode=ok
                        if not ok and latestTstamp:
                            # Something went wrong - rename Backup to Latest 
                            cmd=self.transport.mkCmd("mv Backup_%s Latest_%s" % (
                                latestTstamp,
                                latestTstamp
                            ))
                            ok, code = rim.runCmd(self.log, cmd)
                            if not ok:
                                self.log("Fatal - could not move latest back!!!")
                if not returnCode:
                    # something failed - remove anything we created on the backup target
                    cmd=self.transport.mkCmd("rm -rf _Backup_*")
                    rim.runCmd(self.log, cmd)
            if returnCode:
                self.logErr("Backup successfull : [%s]\n" % self.timesuffix, "success")
        return returnCode
    #
    # stop any ongoing backup
    #
    def stop(self):
        if self.lockit():
            self.unlockit()
            return True
        #
        # We try to kill any rsync process for 10 seconds.
        # That is it and should provide a good exit with the removal of the
        # backups files on the server (see start() above).
        #
        for i in range(10):
            os.system("killall rsync");
            os.sleep
            time.sleep(1)
        #
        # Then try to get the lock again
        #
        if self.lockit():
            self.unlockit()
            return True
        #
        # Still not gone...
        # Kill the python parent
        #
        pid=int(open(pidFile, "r").read())
        os.killpg(pid, signal.SIGTERM)
        time.sleep(1)
        os.killpg(pid, signal.SIGKILL)
        time.sleep(1)
        if not self.lockit():
            # could not kill that process
            self.logErr("Could not stop backup process pid %d" % (pid))
            return False
        #
        # clean up pid file by lock/unlock
        #
        self.lockit()
        self.unlockit()
        self.logErr("Backup stoppped successfully")
        return True
    ##########################################################################
    #
    #   Recovery functions
    #
    ##########################################################################
    def recover(self, timestamp="latest"): # timestamp is either 0 which means latest or a datetime of the user specified time
        #
        self.write_status("starting")
        blist=self.getBackups();
        if len(blist) == 0 :
            self.logerr("No backups found on the server.")
            return False
        #
        # Latest
        if timestamp == 'latest':
            dstDir="Latest_%s" % self.getLatestTstamp()
        else:
            #
            # figure out the closest (i.e. the next older) backup
            if not timestamp in blist:
                self.log( "Backup '%s' not found on server." % timestamp)
                return False
            dstDir=timestamp
        #
        # position into the root and start the recovery
        # The caller script will have made sure we are root and that 
        # the pre and post recover hooks to components have been run
        #
        os.chdir('/')
        #
        # execute recovery in dry-run mode of all configured directories
        #        
        self.write_status("estimating")
        cmd=self.transport.inCmd.safe_substitute({
            "OPTIONS" : "--dry-run",
            "DSTDIR"  : dstDir
        })
        results=[]
        ok, ret = rim.runCmd(self.log, cmd, out=results)
        if not ok:
            self.logErr( "Failed to access size of recovery. Aborting")
            return False
            
        # get the size and file count from previous cmd output
        (size, allFiles) = self.getThisSizeAndFiles("\n".join(results))
        self.log( "size %d , files %d" % (size, allFiles))
        #
        if allFiles == 0:
            self.logerr("Nothing to do.", "success")
            return True
        #
        # Now - do the recovery
        #
        self.logErr("Recovering from backup", "recovering")
        cmd=self.transport.inCmd.safe_substitute({
            "OPTIONS" : "",
            "DSTDIR"  : dstDir
        })
        self.log(cmd)
        child = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        line=child.stdout.readline()
        theseFiles=0
        p1=re.compile('to-check=')
        p2=re.compile('Number of files:')
        ppct=-1
        while len(line):
            m=p1.search(line)
            if m:
                toCheck=int(line[m.span()[1]:].split('/')[0])
                totalToCheck=int(line[m.span()[1]:].split('/')[1].split(')')[0])
                theseFiles=totalToCheck-toCheck
            else:
                m=p2.search(line)
                if m:
                    theseFiles=int(line[m.span()[1]+1:])
            if allFiles > 0:                  
                pct=((theseFiles)*100/allFiles)
                if pct != ppct:
                    self.log("%d%%" % pct)                            
                    open(pctFile, "w").write("%d" % pct)
                    ppct=pct
            line=child.stdout.readline()
        exitCode=child.wait()
        self.log("Recovery exitCode is %d" % exitCode)
        time.sleep(2)
        #
        # we need to restore all of the permissions by scanning the individual 
        # directory for a .ownership file
        #
        self.logErr("Recovering permissions on files...", "permissions")
        dirs=self.getDirList()
        for d in dirs:
            self.log("   %s" % d[0])
            cmd="cd /%s && bash %s 2>/dev/null 1>&2" % (d[0], recFile)
            ok, exitCode = rim.runCmd(self.log, cmd)
            if not ok: return False
        # success - resert the recovery flag
        self.logErr("Recovery successfull : [%s]\n" % self.timesuffix, "success")
        prev=self.setRecover(False)
        self.log("Recover transisioned from '%s' to '%s'" % (prev, False))
        return True 
           
def getBackup():
    return Backup() 
            
         
if __name__ == '__main__':
    backup=Backup()
    print backup.deleteOldest();

