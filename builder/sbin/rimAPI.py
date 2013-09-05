#!/usr/bin/env python

""" 
Implement the restful json api to rim config space

"""
import simplejson as json
import pycurl
import sys
import cStringIO

class RimAPI():
    def __init__(self, log, address, port):
        self.ip=address
        self.port=port
        self.c=pycurl.Curl()
        self.c.setopt(self.c.URL, 'http://%s:%d/getSystemInfo' % (address, port))
        self.c.setopt(self.c.CONNECTTIMEOUT, 2)
        self.c.setopt(self.c.TIMEOUT, 4)
        self.buf=cStringIO.StringIO()
        self.c.setopt(self.c.WRITEFUNCTION, self.buf.write)
        self.log=log
        self.log("curl to %s:%d - initialized" % (self.ip, self.port))
        self.changed=False
        
    def getCfg(self):
        try:
            self.c.perform()
            self.root = json.loads(eval(self.buf.getvalue()))
            return self.root
        except:
            return None

    # recursively dril down the config to the assigned element
    def nextTok(self, pos, arg):
        fields=arg.split(':')
        if len(fields) > 0:

            field=fields[0]
            try:
                equalpos=field.index('=')
                value=field[equalpos+1:]
                field=field[0:equalpos]
            except:
                equalpos=None
            
            if pos.has_key(field):
                # check for an assignment
                if equalpos:
                    try:
                        if pos[field] != eval(value):
                            pos[field]=eval(value)
                            self.changed=True
                    except:
                        if pos[field] != value:
                            pos[field]=value
                            self.changed=True
                else:
                    if len(fields) > 1:
                        self.changed=self.nextTok(pos[field], arg[len(field)+1:]) or self.changed
                    else:
                        log(pos[field])
            else:
                log("Invalid field '%s' specified\n" % field)
                return self.changed
        return self.changed  

    def set(self, var, value):
        return self.nextTok(self.root, "%s=%s" % (var, value))

    def get(self, var):
        return self.nextTok(self.root, "%s" % var)

    def sync(self):
        if self.changed:
            self.c.setopt(self.c.POST, 1)
            self.c.setopt(self.c.POSTFIELDS, "json=%s" % json.dumps(self.root))
            self.c.perform()
            self.changed=False
        
if __name__ == '__main__':
    def log(s):
        print "%s" % s
    api=RimAPI(log, sys.argv[1], int(sys.argv[2]))
    print api.getCfg()
    for arg in range(3, len(sys.argv)): api.get(sys.argv[arg])
        
