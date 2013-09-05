#!/usr/bin/env python2/>
import socket,binascii,os
import struct
from math import ceil
from sys import exit
from isos import *
import rim

host = ''
port = 69

class tftpServer():

    def __init__(self, hosts, imgd, cfg):
        self.s=None
        self.isos=isos()
        self.hosts=hosts
        self.imgd=imgd
        self.cfg=cfg
        self.log=rim.logger("tftp").log
        
    def group(self, s, n): 
        return [s[i:i+n] for i in xrange(0, len(s), n)]
    
    def findHostByIp(self, ip):
        for mac in self.hosts:
            if self.hosts[mac].Ip == ip: return self.hosts[mac]
        return None
    
    # handle a message from a tftp client
    def handleMsg(self, message, address):
        self.log("message from %s - [%s]" % (address, message[0:1]))
        ip, port = address
        host=self.findHostByIp(ip)
        if not host:
            self.log("Unknown host")
        elif message.startswith('\x00\x01'): #RRQ
            self.log("RRQ - ")
            message=message.split('\x00')
            host.tftpName=message[1][1:]
            self.log("RRQ - '%s' " % host.tftpName)
            host.iso=self.isos.probe(host.Iso)
            if host.iso:
                host.fileName=host.iso.filePath(host.tftpName)
                self.log("%s wants %s [%s]" % (address,host.tftpName,host.fileName))
                if not len(host.fileName):
                    self.log("No such file");
                    self.s.sendto('\x00\x05\x00\x01no such file exists',address)
                    return
                fsize=os.path.getsize(host.fileName)
                self.log("file size of %s" % fsize)
                self.s.sendto('\x00\x06blksize\x00512\x00tsize\x00%s\x00' % fsize,address)
        elif message.startswith('\x00\x04'): #OptACK
            self.log("OptACK")
            last=address
            # if we restart in ther middle of a tranfer, we may get stray OptAcks...
            # bail out if so
            if not host.fileName: return 
            f=open(host.fileName,'r')
            fileName=host.fileName.split("/")[-1]
            data=f.read()
            f.close()
            dataset=self.group(data,512)
            if len(dataset) > 65534: self.log("Won't work, too large... >64MB")
            # add another empty chunk if the last one is 512 bytes
            if len(dataset[-1]) == 512:
                self.log("Padding with 0 byte chunck!")
                dataset.append("")
            for index,chunk in enumerate(dataset):
                acked=False
                retries=0
                msg='\x00\x03'+binascii.unhexlify(hex(index+1)[2:].rjust(4,'0'))+chunk
                while not acked:
                    try:
                        self.s.sendto(msg,address)
                    except:
                        raise
                    try:
                        ack, address=self.s.recvfrom(128)
                    except socket.error as err:
                        self.log("Index %s ack error '%s;" % (index, err))
                        retries=retries+1
                        if retries > 10:
                            self.log("Retried 10 times - aborting")
                            return
                        continue
                    ackNum=int("0x%s" % binascii.hexlify(ack)[4:8], 16)
                    if ackNum == int(index)+1:
                        acked=True
                    else:
                        self.log("index '%s' ack '%d'" % (index+1, ackNum))
                        
                        
            self.log("Done with '%s'" % host.fileName)
            if host.iso.isInitrd(fileName) :
                # stop serving this guy. It might wantto reboot into new version
                # this will force a reload of config form parent
                self.imgd.setServe(self.cfg, host.Mac, False)
    def initHandles(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(0.5)
        s.bind((host, port))
        self.log("Initialized on port %d, socket %d" % (port, s.fileno()))
        self.s=s
        
    def chkHandles(self, rlist, wlist, xlist):
        if self.s and self.s.fileno() in rlist:
                message, address = self.s.recvfrom(8192)
                self.handleMsg(message, address)
        return True
                
    def setHandles(self, rlist, wlist, xlist):
        if self.s:
            rlist.append(self.s.fileno())
        
    def releaseHandles(self):
        if self.s:
            self.s.close()
