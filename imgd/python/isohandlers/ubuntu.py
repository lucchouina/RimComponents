
import os
import sys
import time
import rim

from iso import *

default="""
DEFAULT install
LABEL install
menu label ^Install to the hard disk automatically
kernel %s
append ip=dhcp preseed/url=%s initrd=%s root=/dev/ram lacpi pci=routeirq  persistent vga=normal log_host=%s BOOT_DEBUG=%d ks=%s  --
TIMEOUT 0
PROMPT 0
"""
#append ip=dhcp preseed/url=%s initrd=%s root=/dev/ram lacpi pci=routeirq  persistent vga=normal log_host=%s BOOT_DEBUG=%d ks=%s  --
class ubuntuIso(iso):

    def __init__(self, mntpt):
        self.mntpt=mntpt
        iso.__init__(self)
        self.log=rim.logger("ubuntu").log

    def filePath(self, tftpName):
        fileName=tftpName.split('/')[-1]
        if fileName == "kernel":
            # need to serve a nfsroot enabled kernel
            return "%s/install/vmlinuz" % (self.mntpt)
            return "%s/install/netboot/ubuntu-installer/i386/linux" % (self.mntpt)
        elif fileName == "initrd":
            #return "%s/install/initrd.gz" % (self.mntpt)
            return "%s/install/netboot/ubuntu-installer/i386/initrd.gz" % (self.mntpt)
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
        
    def netPreseed(self):
        pfile="%s/preseed/ubuntu-server.seed" % (self.mntpt)
        lines=(open(pfile, "r").read()+"""
d-i mirror/protocol string http
d-i mirror/http/hostname string %s:81
d-i mirror/http/directory string %s
d-i mirror/suite string lucid
d-i mirror/http/proxy string
""" % (self.myIp, self.mntpt)).split("\n")
        newfile="/tmp/%s.seed" % self.name
        f=open(newfile, "w")
        for line in lines:
            fields=line.split()
            if len(fields) > 1 and fields[1]=="base-installer/kernel/override-image":
                continue
            if len(fields) > 0 and fields[0]=="tasksel":
                f.write("tasksel tasksel/first multiselect standard, ubuntu-server\n")
                f.write("d-i pkgsel/update-policy select none\n")
                continue
            f.write("%s\n" % line)
        f.close()
        return newfile

    def defaultPath(self):
        initrd="initrd"
        kernel="kernel"
        pfile="http://%s:81%s" % (self.myIp, self.netPreseed())
        ks="http://%s:81/%s" % (self.myIp, self.nfsKs())
        #
        # we are pointing the logger to ourselves for debug
        # set BOOT_DEBUG appropriately
        #
        defStr=default % (kernel, pfile, initrd, self.myIp, 2, ks)
        print defStr
        #
        # we need to modify the basic cd/usb isolinux to inforce nfs install
        #
        # we need to modify the basic cd/usb isolinux to inforce nfs install
        # the init->scrathinstall will be looking for ip=dhcp as a trigger
        #
        f=open("%s/isolinux/isolinux.cfg" % (self.mntpt), "r")
        newpath="/tmp/%s.cfg" % self.name
        open(newpath, "w").write(defStr)
        return newpath
        
    def nfsKs(self):
        lines=open("%s/isolinux/ks.cfg" % self.mntpt, "r").read().split('\n')
        newpath="/tmp/%s.ks" % self.name
        new=open(newpath, "w")
        for line in lines:
            fields=line.split()
            if len(fields) > 0 :
                # substitue cdrom media directive for http
                if fields[0]=='cdrom':
                    new.write("url --url=http://%s:81/%s/\n" % (self.myIp, self.mntpt))
                    #new.write("nfs --server %s --dir %s\n" % (self.myIp, self.mntpt))
                elif fields[0]=='network':
                    new.write("network --bootproto=dhcp --device=eth0\n")
                else:
                    new.write("%s\n" % line)
        new.close()
        return newpath

    def kernelPath(self, name):
        return "%s/install/netboot/ubuntu-installer/i386/linux" % (self.mntpt)

    def initrdPath(self, name):
        return "%s/install/netboot/ubuntu-installer/i386/initrd.gz" % (self.mntpt)

def probe(mntpt):
    # look for the tell tell signs of a rim iso
    iso=ubuntuIso(mntpt)
    if not iso.use(): return None
    if(os.path.exists("%s/install" % mntpt)): return iso
    return None
