#!/usr/bin/env python
#

""" backup.py

JSON for reading/updating Backup Settings

"""
import os
import sys
import glob
import imp
import simplejson as json

from settings.command import *
from settings.utils import *
import backups

def get():
    """ 
       retrieve Backup settings 
       We simply read from the json back config file. 
    """
    result={}
    backup=backups.Backup();
    result=backup.getCfg()
    return result

#
# run a command in the background 
# detach from controlling terminal 
#
def runcmd(cmd):
    backup=backups.Backup();
    cmd="echo '%s 2>>%s 1>&2' | /usr/bin/at -qb now 1>/dev/null 2>&1" % (cmd, backups.logFile)
    backup.log("cmd=[%s]" % cmd)
    retCode=subprocess.call(cmd, shell=True)
    if retCode != 0:
        backup.log("'%s' failed with exit code %d" % (cmd, retCode))

def set(old, new):

    """ update backup settings
    """
    
    backup=backups.Backup();
    new_values=new[backups.myId]

    # save a cleaned up version of the set
    backup.writeCfg(cleanCfg("{%s}" % schema(), backups.myId, new_values));
        
    enabled     = new_values[backups.ENABLED_ATTR]
    
    if new_values[backups.RECOVER_ATTR]:
        return  backup.recovercmd()
            
    if old[backups.myId][backups.ENABLED_ATTR] != enabled:
        if enabled:
            return backup.startcmd()
        else:
            return backup.stopcmd()
    
    if new_values.has_key(backups.COMMAND_ATTR):
        cmd=new_values[backups.COMMAND_ATTR]
        if new_values.has_key(backups.PASSWORD_ATTR): 
            pw=new_values[backups.PASSWORD_ATTR]
        else: 
            pw=""
        if   cmd == "run" :     runcmd("/sbin/run-backups %s" % pw)
        elif cmd == "stop":     runcmd("/sbin/stop-backups")
        elif cmd == "test":     runcmd("/sbin/testBackups %s" % pw)

    return ""

def validate(values, name, errors):

    backup=backups.Backup()
    
    # override persistant config with this one.
    backup.setRunCfg(values)
    
    if values.has_key(backups.PASSWORD_ATTR): 
        pw=values[backups.PASSWORD_ATTR]
    else: 
        pw=""

    rec=False
    if values.has_key(backups.COMMAND_ATTR) and len(values[backups.COMMAND_ATTR]): 
        if values[backups.COMMAND_ATTR]=="recover":
            rec=True
    if not rec: 
        rec=values[backups.RECOVER_ATTR]
        
    if not values[backups.ENABLED_ATTR] and not rec:
        return True;

    msg=backup.transport.validate(pw)
    if len(msg):
         errors[name]=msg
         return False
    return True
    
def test(values, name, errors):
    return validate(values, name, errors)
    
def cfgKey():
    return backups.myId
    
# translate config during upgrade
# We moved the initmode under the system block now
def translate(incoming, outgoing):
    if incoming.has_key(backups.myId):
        oldCfg=incoming[backups.myId]
        if not outgoing.has_key(backups.myId):
            outgoing[backups.myId]={}
        newCfg=outgoing[backups.myId]
        # translate the old rsync config into the new transport based format
        if oldCfg.has_key('Server'):
            newCfg['Recover']=oldCfg['Recover']
            # localhost is not a good idea, need to strip this from old config
            if oldCfg['Server'] == 'localhost':
                oldCfg['Server']=""
                oldCfg['UserName']=""
            # only tranfer if configured
            newCfg['Directory']="backups"
            newCfg['Type']='ssh'
            for field in [ 'Server', 'UserName', 'Password', 'Status', 'Msg' ]:
                newCfg[field]=oldCfg[field]
        else:
            newCfg=oldCfg        

# transport config block
# may be handled by an external handler in the future
transport="""
    "Type": {
        "order" : "1",
        "type":"str",
        "appmode":true,
        "title":"Backup server type",
        "description":"Type of transport to use to access this server",
        "enum":
        [
            %s
        ]
    },
    "Server":
    {
        "order" : "2",
        "appmode":true,
        "type":"str",
        "title":"Server"
    }, 
    "UserName":
    {
        "order" : "3",
        "appmode":true,
        "type":"str",
        "title":"User name"
    }, 
    "Password":
    {
        "order" : "4",
        "type":"str",
        "appmode":true,
        "title":"Password"
    },
    "Directory":
    {
        "order" : "5",
        "type":"str",
        "appmode":true,
        "title":"Directory/Target",
        "Desc":"Directory (rsync and nas) or target name (iscsi) to use for the backup"
    }, 
    "Status":
    {
        "type":"str",
        "access":"read-only",
        "appmode":true,
        "title":"Current status of this transport",
        "Desc":"Global will regularily poll the status of enabled transport"
    },
    "Progress":
    {
        "type":"str",
        "appmode":true,
        "access":"read-only",
        "title":"Process status in percent done"
    }, 
    "Msg":
    {
        "type":"str",
        "appmode":true,
        "access":"read-only",
        "title":"Last error encountered during backup"
    }
"""

def getTtypes():
    tstr=""
    sep=""
    for infile in sorted(glob.glob('%s/transports/*.py' % sys.path[0])):
        fname = os.path.basename(infile)[:-3]
        mod=imp.load_source(fname, infile) 
        if hasattr(mod, "myTname"):
            tstr='%s%s "%s"' % (tstr, sep, mod.myTname())
            sep=","
    return tstr

def schema():
    return ("""
        "%s": {
            "type":"map",
            "appmode":true,
            "title":"Backup configuration",
            "description":"Backup configuration",
            "mapping":
            {
                "Enabled": 
                {
                    "order":"1",
                    "appmode":true,
                    "type":"bool",
                    "required":true,
                    "title":"Enable backups"
                }, 
                "Command":
                {
                    "type":"str",
                    "appmode":true,
                    "access":"write-only",
                    "title":"Command to execute execution"
                },
                "Recover":
                {
                    "type":"bool",
                    "order":"2",
                    "appmode":true,
                    "title":"Recover from latest backup"
                },
                    """ % backups.myId)+(transport % getTtypes())+"""
            }
        }
""" 

if __name__ == '__main__':
    print json.dumps(get())
