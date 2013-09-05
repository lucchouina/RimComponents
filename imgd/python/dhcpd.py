#!/usr/bin/env python

import socket, binascii,time
import string
from sys import exit
from settings.handlers import ipinfo
from isos import *
import rim

host = ''
port = 67
dnsserver='8.8.8.8'
leasetime=86400 #int

# get our own ip config
ipjson=ipinfo.get()
ipcfg=rim.jsonToObject(ipjson)

# set up default values
tftpserver=ipcfg.IPAddress
serverhost=tftpserver
broadcast=ipinfo.getBcast(ipjson)
subnetmask=ipcfg.SubnetMask
router=ipcfg.Gateway

pxefilename='/netboot/pxelinux.0'

# some tables
OptionsTblDesc={
    0	: "Pad	1 octet",
    1	: "Subnet Mask",
    2	: "Time Offset	",
    3	: "Router",
    4	: "Time Server",
    5	: "Name Server",
    6	: "Domain Name",
    7	: "Log Server",
    8	: "Cookie Server	",
    9	: "LPR Server	",
    10	: "Impress Server	",
    11	: "Resource Location Server	",
    12	: "Host Name",
    13	: "Boot File Size",
    14	: "Merit Dump File",
    15	: "Domain Name	",
    16	: "Swap Server	",
    17	: "Root Path	",
    18	: "Extensions Path",
    50  : "Requested IP",
    51  : "IP Address Lease Time",
    52  : "Option Overload",
    53  : "DHCP Message Type",
    54  : "Server Identifier",
    55  : "Parameter Request List",
    56  : "Message",
    57  : "Maximum DHCP Message Size",
    58  : "Renewal (T1) Time Values",
    59  : "Rebinding (T2) Time Value",
    60  : "Vendor class identifier",
    61  : "Client-identifier",
    66  : "TFTP server name",
    67  : "Bootfile name",
    255	: "End"

}


class dhcpServer():

    def __init__(self, hosts, tftp):
        self.s=None
        self.hosts=hosts
        for mac in hosts:
            hosts[mac].xid=""
        self.tftp=tftp
        self.isos=isos()
        self.log=rim.logger("dhcp").log
        
    def findOption(self, bytes, opt):
        pos=0
        while pos < len(bytes):
            option=int(bytes[pos:pos+2], 16)
            size=int(bytes[pos+2:pos+4], 16)
            self.log("Option [%d] - len %d" % (option, size))
            if option == 55:
                for i in range(0,size):
                    option=int(bytes[pos+4+(i*2):pos+6+(i*2)], 16)
                    self.log("     subtion - [%d]" % (option))
                    if option == opt:
                        return True
            pos=pos+4+(size*2)
        return False
        
    def printOptions(self, bytes):
        pos=0
        while pos < len(bytes):
            option=int(bytes[pos:pos+2], 16)
            size=int(bytes[pos+2:pos+4], 16)
            self.log("Option [%d] - len %d" % (option, size))
            pos=pos+4+(size*2)
        return None
        
    # generator that produced an array of byte sequences, one sequence per dhcp 
    dhcpfields=[1,1,1,1,4,2,2,4,4,4,4,6,10,192,4,"msg.rfind('\xff')",1,None]
    def slicendice(self, msg,slices=dhcpfields): #generator for each of the dhcp fields
        for x in slices:
            if str(type(x)) == "<type 'str'>": 
                x=eval(x)
            yield msg[:x]
            msg = msg[x:]
          
    def makeMac(self, MAC):
        return "%s:%s:%s:%s:%s:%s" % (
            MAC[:2].upper(),
            MAC[2:4].upper(),
            MAC[4:6].upper(),
            MAC[6:8].upper(),
            MAC[8:10].upper(),
            MAC[10:12].upper()
        )
          
    # address lookup - return false if not handled by us
    def getAddress(self, mac):
        if mac in self.hosts:
            host=self.hosts[mac]
            self.log("Host found '%s' for '%s' - serve is %s" % (host.Ip, mac, host.Serve)) 
            # check if should respond this one time
            return host
        return None

    # handle a message from a dhcp client
    def handleMsg(self, message):
    
        data=None

        # split message in its components
        hexmessage=binascii.hexlify(message)
        messagesplit=[binascii.hexlify(x) for x in self.slicendice(message)]
        dhcpopt=messagesplit[15][:6] #hope DHCP type is first. Should be.
        mac=self.makeMac(messagesplit[11])
        self.log("message from '%s'" % mac)
        host=self.getAddress(mac)
        if host:
            #
            # we handle address assignment all the time
            # we handle boot files only when Server is True
            # Serve will become False after tftp file has been served
            #
            self.printOptions(messagesplit[15])
            self.log("found = %s" % self.findOption(messagesplit[15], 67))
            if host.Serve or not self.findOption(messagesplit[15], 67):
                self.log("options are '%s'" % messagesplit[15])
                # make sure we setup the right iso
                if host.Serve:
                    host.iso=self.isos.probe(host.Iso)
                    pxefilename=host.iso.pxefilename()
                else:
                    host.iso=None
                if dhcpopt == '350101':
                    self.log("DHCP Discover -> Offer")
                    data='\x02\x01\x06\x00'+binascii.unhexlify(messagesplit[4])+'\x00\x04'
                    data+='\x80\x00'+'\x00'*4+socket.inet_aton(host.Ip)
                    data+=socket.inet_aton(serverhost)+'\x00'*4
                    # CHADDR (Client Hardware Address)
                    data+=binascii.unhexlify(messagesplit[11])+'\x00'*10+'\x00'*192
                    data+='\x63\x82\x53\x63'+'\x35\x01\x02'+'\x01\x04'
                    data+=socket.inet_aton(subnetmask)+'\x36\x04'+socket.inet_aton(serverhost)
                    data+='\x1c\x04'+socket.inet_aton(broadcast)+'\x03\x04'
                    data+=socket.inet_aton(router)+'\x06\x04'+socket.inet_aton(dnsserver)
                    data+='\x33\x04'+binascii.unhexlify(hex(leasetime)[2:].rjust(8,'0'))
                    host.xid=messagesplit[4]
                    self.log("xid is '%s' " % host.xid)
                    if host.iso:
                        data+='\x42'+binascii.unhexlify(hex(len(tftpserver))[2:].rjust(2,'0'))+tftpserver
                        data+='\x43'+binascii.unhexlify(hex(len(pxefilename)+1)[2:].rjust(2,'0'))
                        data+=pxefilename+'\x00\xff'

                elif dhcpopt == '350103':
                    self.log("DHCP REQUEST")
                    if host.xid == messagesplit[4]:
                        data='\x02\x01\x06\x00'+binascii.unhexlify(messagesplit[4])+'\x00'*8
                        data+=binascii.unhexlify(messagesplit[15][messagesplit[15].find('3204')+4:messagesplit[15].find('3204')+12])
                        data+=socket.inet_aton(serverhost)+'\x00'*4
                        data+=binascii.unhexlify(messagesplit[11])+'\x00'*202
                        data+='\x63\x82\x53\x63'+'\x35\x01\05'+'\x36\x04'+socket.inet_aton(serverhost)+'\x06\x04'+socket.inet_aton(dnsserver)
                        data+='\x01\x04'+socket.inet_aton(subnetmask)+'\x03\x04'
                        data+=socket.inet_aton(router)+'\x33\x04'
                        data+=binascii.unhexlify(hex(leasetime)[2:].rjust(8,'0'))
                        if host.iso:
                            data+='\x42'+binascii.unhexlify(hex(len(tftpserver))[2:].rjust(2,'0'))
                            data+=tftpserver+'\x43'+binascii.unhexlify(hex(len(pxefilename)+1)[2:].rjust(2,'0'))
                            data+=pxefilename+'\x00\xff'
                    else:
                        self.log("Not my XID '%s' versus '%s'" % (host.xid, messagesplit[4]))
        else:
            self.log("Unknown host")
        return data
        
    def initHandles(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind((host, port))
        self.log("Initialized on port %d, socket %d" % (port, s.fileno()))
        self.s=s

    def chkHandles(self, rlist, wlist, xlist):
        if self.s and self.s.fileno() in rlist:
            try:
                message, address = self.s.recvfrom(8192)
                if not message.startswith('\x01') and not address[0] == '0.0.0.0':
                   return True #only serve if a dhcp request
                data=self.handleMsg(message) #handle request
                if data:
                   self.s.sendto(data,('<broadcast>',68)) #reply
            except socket.error as msg:
                self.log("sendto : %s" % msg)
        return True
 
    def setHandles(self, rlist, wlist, xlist):
        if self.s:
            rlist.append(self.s.fileno())
            
    def releaseHandles(self):
        if self.s:
            self.s.close()
