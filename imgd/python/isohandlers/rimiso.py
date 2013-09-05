
import os
import sys
import time
import rim
from iso import *

class rimIso(iso):

    def __init__(self, mntpt):
        self.mntpt=mntpt
        iso.__init__(self)

    def filePath(self, tftpName):
        fileName=tftpName.split('/')[-1]
        if fileName == "kernel":
            return "%s/kernel" % (self.mntpt)
        elif fileName == "initrd":
            return "%s/initrd" % (self.mntpt)
        elif fileName == "default":
            return self.defaultPath()
        elif os.path.exists(tftpName):
            return tftpName
        else: 
            return ""
            
    def isInitrd(self, tftpName):
        if tftpName.split('/')[-1] == 'initrd': return True
        return False

    # rim uses the one from the package itself
    def pxefilename(self):
        return '/netboot/pxelinux.0'

    def defaultPath(self):
        #
        # We use what's there but we need to modify the basic cd/usb isolinux to inforce nfs install
        # the init->scrathinstall will be looking for ip=dhcp as a trigger
        # The mountpoint is already exported by the iso class use()/probe() methods.
        #
        f=open("%s/isolinux/isolinux.cfg" % (self.mntpt), "r")
        newpath="/tmp/%s.cfg" % self.name
        new=open(newpath, "w")
        lines=f.read().split("\n")
        f.close()
        for line in lines:
            fields=line.split()
            if len(fields) > 0 :
                if fields[0]=='APPEND':
                    newfields=['APPEND', 'ip=dhcp', 'mount=%s' % (self.mntpt), 'server=%s' % self.myIp]
                    for f in fields[1:]:
                        # force serial console for this type of bringup
                        #
                        if f != "console=tty" and f != "quiet":
                            newfields.append(f)
                    options=" ".join(newfields)
                    new.write("%s\n" % options)
                    #self.log("options='%s'"  % options)
                elif fields[0]=='TIMEOUT':
                    new.write("TIMEOUT 50\n")
                    new.write("TOTALTIMEOUT 100\n")
                elif fields[0]=='PROMPT':
                    new.write("PROMPT 0\n")
                else:
                    new.write("%s\n" % line)
        new.close()
        return newpath

def probe(mntpt):
    # look for the tell tell signs of a rim iso
    iso=rimIso(mntpt)
    if not iso.use(): return None
    if os.path.exists("%s/bom.xml" % mntpt): return iso
    return None
