#!/usr/bin/env python
#

""" backup.py

JSON for reading/updating Backup Settings

Attributes are:

UserName: User name to use for ssh sesssion
Enabled: Boolean to enable backups
Server: IP address of the backup server

"""
import os
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
    backups.REC_LIST_ATTR,
    blist=[]
    nlist=[]
    backup=backups.Backup();
    try:
        blist=backup.getBackups()
    except:
        pass
    for entry in reversed(blist):
        if len(entry[16:]): nlist.append(entry[16:])
    result[backups.REC_LIST_ATTR]=nlist  
    result[backups.REC_PREFIX_ATTR]="backups"
    return result
        
def set(old, new):
    # all read only
    return ""

def cfgKey():
    return backups.recId
    
def schema():
    return """
        "%s": {
            "type":"map",
            "hidden":"true",
            "title":"Backup recovery",
            "description":"Readonly configruation needed for managing recoveries.",
            "mapping":
            {
                "%s":
                {
                    "type":"array",
                    "title":"%s",
                    "description":"list of available backups.",
                    "items" : {
                        "type":"str",
                        "title":"%s",
                        "description":"Date and time this backup was performed"
                    }
                },
                "%s":
                {
                    "type": "str",
                    "title":"Target Prefix",
                    "description":"Filesystren prefix for accessing a backup relative to backup user HOME."
                }
            }
        }
""" % (
    backups.recId, 
    backups.REC_LIST_ATTR, 
    backups.REC_LIST_ATTR, 
    backups.REC_ENTRY_DATETIME_ATTR, 
    backups.REC_PREFIX_ATTR
)

if __name__ == '__main__':
    print json.dumps(get())
