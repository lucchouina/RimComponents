#!/usr/bin/env python
#

""" lxc.py

JSON for controlling the container instances

"""
import os
import json

from settings.command import *
from settings.utils import *
from settings.handlers import system

myId="Containers"
ENABLED_ATTR="Enabled"
SIZE_ATTR="Size"
IPBASE_ATTR="IpBase"
PREVLEVEL_ATTR="PrevLevel"
CONF_FILE = "/etc/containers.conf"
# need a file to flag the fact we are running inside a container
FLAG_FILE = "/iamacontainer"

def get():
    return json.load(open(CONF_FILE, "r"))

def set(old, new):
    # if anything changes we restart
    # caller will not call here if nothing changed
    if new[myId][ENABLED_ATTR]:
        new[myId][PREVLEVEL_ATTR]=initDefault()
        run_command("sed -i -e 's/id:5:initdefault:/id:8:initdefault:/g' /etc/inittab")
        run_command("sed -i -e 's/id:3:initdefault:/id:8:initdefault:/g' /etc/inittab")
        # record current level in PrevLevel
        cmd = "sleep 1; telinit 8\n"
    else:
        if system.isInitmode(new[system.myId]):
            run_command("sed -i -e 's/id:8:initdefault:/id:3:initdefault:/g' /etc/inittab")
            cmd = "telinit 3\n"
        else:
            run_command("sed -i -e 's/id:3:initdefault:/id:5:initdefault:/g' /etc/inittab")
            cmd = "telinit 5\n"
    json.dump(new[myId], open(CONF_FILE, "w"), sort_keys=True, indent=4);
    return cmd

def getSize(cfg):
    return cfg[SIZE_ATTR]
    
def getPrevLevel(cfg):
    return cfg[PREVLEVEL_ATTR]
    
def getIpBase(cfg):
    return cfg[IPBASE_ATTR]
    
def setEnabled(cfg, state):
    cfg[ENABLED_ATTR]=state
    
def schema():
    return """
        "%s": {
            "type":"map",
            "order":"2",
            "title":"Container configuration for load testing",
            "description":"We use linux containers to instanciate a large number of clients for server test",
            "mapping":
            {
                "%s": {
                    "type":"bool",
                    "order":1,
                    "appmode":true,
                    "required":true,
                    "title": "Enable the simulation",
                    "description":"This will trigger the instanciations of N client containers"
                },
                "%s":
                {
                    "order":2,
                    "type":"int",
                    "required":true,
                    "appmode":true,
                    "title":"Previous Level",
                    "description":"Run Level prior to level 8"
                },
                "%s":
                {
                    "order":3,
                    "type":"int",
                    "required":true,
                    "appmode":true,
                    "title":"Number of instance",
                    "description":"Number of client to instanciate"
                },
                "%s":
                {
                    "order":4,
                    "type":"str",
                    "subtype":"ip",
                    "required":true,
                    "appmode":true,
                    "title":"Base IP",
                    "description":"Base IP address to assign to each client"
                }
            }
        }
""" % (myId,ENABLED_ATTR,PREVLEVEL_ATTR,SIZE_ATTR,IPBASE_ATTR)

def cfgKey():
    return myId

    
if __name__ == '__main__':
    print json.dumps(get_ipinfo())
    
