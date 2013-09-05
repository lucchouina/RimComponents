#!/usr/bin/env python
import XenAPI
import sys
import os
import pwd
import time
import rim
import selector
import paramiko
import socket
import subprocess
from datetime import datetime

from settings.handlers import ci

"""
    Manage the serial consoles of the VMs in the CI pipe.
    We use a combination of xenApi and xmconsole, socat, to 
    record i/o to from console devices and to enable telnet access to 
    them as well.
    
    Multiple telnet clients can interact with each console and all i/o
    is also logged to a console log file.
    
    Telnet client are kept alive accross vm reboots. The mail loop
    will rescan the xenapi db for the vm host and domid with each 
    vm restarts. So this shoudl also work accross migrations.
    
"""

class Respawner():

    
    def __init__(self, cmd):
        self.log=rim.logger("respawner").log
        self.log("cmd='%s'" % cmd)
        self.child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        
    def initHandles(self):
        return True
        
    def setHandles(self, rlist, wlist, xlist):
        rlist.append(self.child.stdout)
        
    def chkHandles(self, rlist, wlist, xlist):
        if self.child.stdout in rlist:
            output=self.child.stdout.read()
            if not len(output):
                code=self.child.wait()
                self.log("child exited - with %d - respawning" % code)
                self.child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return True
    
    def releaseHandles(self):
        self.child.kill()
        
class inOut():
    
    def __init__(self, infd, telnet):
        self.log=rim.logger("inOut").log
        self.infd=infd
        self.telnet=telnet
        
    def initHandles(self):
        return True

    def addUs(self, us):
        self.infd=us
        self.log=rim.logger("inOut[%d]" % self.infd.fileno()).log

    def setHandles(self, rlist, wlist, xlist):
        if self.infd: rlist.append(self.infd)
        
    def chkHandles(self, rlist, wlist, xlist):
        if self.infd and self.infd in rlist:
            msg=self.infd.recv(1024)
            self.log("New message from Unix socket - len(%d)" % len(msg))
            if not len(msg): return False
            self.telnet.toClients(msg)
        return True

    def releaseHandles(self):
        if self.infd: self.infd.close()
        
class telnet():
    
    def __init__(self, port, logfile, sock, vmName):
        self.log=rim.logger("telnet[%d]" % port).log
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('0.0.0.0',port))
        except :
            self.log("already in use")
            sys.exit(1)
        self.log("listening on port %d" % port)
        s.listen(1)
        self.s=s
        self.clients=[]
        self.logfile=logfile
        self.sock=sock
        self.vmName=vmName
        
    def addUs(self, us):
        self.sock=us
        self.toClients("\n\r** Console to '%s' is back ** \n\r" % self.vmName)
        
    def initHandles(self):
        return True
        
    def toClients(self, msg):
        self.logfile.write(msg.replace("\n", "\n[ %s ]" % datetime.now().ctime()))
        self.logfile.flush()
        for client in self.clients:
            client.send(msg)
            
    def capXchg(self, conn):
    
        DOOPTS = {}
        WILLOPTS    = {}
        ECHO        = chr(1) 
        RCP         = chr(2) 
        SGA         = chr(3) 
        NAMS        = chr(4) 
        NAWS        = chr(31)
        LINEMODE    = chr(34)
        NOOPT       = chr(0)
        IAC         = chr(255) 
        DONT        = chr(254)
        DO          = chr(253)
        WONT        = chr(252)
        WILL        = chr(251)
        DOACK = {
            ECHO: WILL,
            SGA: WILL,
        }
        WILLACK = {
            ECHO: DONT,
            SGA: DO,
            LINEMODE: DONT,
        }
        
        def writecooked(text):
            conn.sendall(text)
            
        def sendcommand(cmd, opt=None):
            if cmd in [DO, DONT]:
                if not DOOPTS.has_key(opt):
                    DOOPTS[opt] = None
                if (((cmd == DO) and (DOOPTS[opt] != True))
                or ((cmd == DONT) and (DOOPTS[opt] != False))):
                    DOOPTS[opt] = (cmd == DO)
                    writecooked(IAC + cmd + opt)
            elif cmd in [WILL, WONT]:
                if not WILLOPTS.has_key(opt):
                    WILLOPTS[opt] = ''
                if (((cmd == WILL) and (WILLOPTS[opt] != True))
                or ((cmd == WONT) and (WILLOPTS[opt] != False))):
                    WILLOPTS[opt] = (cmd == WILL)
                    writecooked(IAC + cmd + opt)
            else:
                writecooked(IAC + cmd)        
                
        for k in DOACK.keys():
            sendcommand(DOACK[k], k)
        for k in WILLACK.keys():
            sendcommand(WILLACK[k], k)

        
    def chkHandles(self, rlist, wlist, xlist):
    
        if self.s in rlist:
            conn, addr = self.s.accept()
            self.clients.append(conn)
            self.log("New connection from %s:%d" % addr)
            self.capXchg(conn)
        for client in self.clients:
            if client in rlist:
                msg=client.recv(1024)
                self.log("Message from client on %d - len(%d)" % (client.fileno(), len(msg)))
                if not len(msg):
                    client.close()
                    del(self.clients[self.clients.index(client)])
                else:
                    if self.sock:
                        self.sock.send(msg)
        return True

    def setHandles(self, rlist, wlist, xlist):
    
        rlist.append(self.s)
        for client in self.clients:
            rlist.append(client)
        
    def releaseHandles(self):
        self.toClients("\n\r** Console to '%s' disconnected ** \n\r" % self.vmName)
        return # we keep the client alive when the mainloop quits

class Console():

    global session
    
    def __init__(self, vmName):
        self.log=rim.logger("ci-console").log
        self.ciCfg=ci.get()
        self.xIp=self.ciCfg['xIP']
        self.login=self.ciCfg["xenLogin"]
        self.pw=self.ciCfg["xenPassword"]
        self.telnetBase=int(self.ciCfg["telnetBase"])
        url="https://%s:443/" % self.xIp
        self.session = XenAPI.Session(url)
        self.session.xenapi.login_with_password(self.login, self.pw)
        self.vmRef=self.session.xenapi.VM.get_by_name_label(vmName)[0]
        self.vmName=vmName
        self.cdir=self.ciCfg['consoleDir']
        self.unixFile="%s/socket.%s" % (self.cdir, self.vmName)
    
    def getHostAndDomain(self):
        hostRef=self.session.xenapi.VM.get_resident_on(self.vmRef)
        try:
            return self.session.xenapi.host.get_address(hostRef), self.session.xenapi.VM.get_domid(self.vmRef)
        except:
            return None, None
        
    def setKeys(self, myXip):
        try:
            home=pwd.getpwuid(os.getuid()).pw_dir
        except:
            home=os.getenv("HOME")
            if not home: 
                home="/home/%s" % getpass.getuser()
        self.log("HOME '%s'" % home)
        rsaKey="%s/.ssh/id_rsa" % home
        hostFile="%s/.ssh/known_hosts" % home
        ssh=paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.log("Checking ssh to '%s@%s'" % (self.login, myXip))

        #
        # setup the keys
        # ssh-keygen [-q] [-b bits] -t type [-N new_passphrase] [-C comment] [-f output_keyfile]
        try:
            open(rsaKey, "r")
            fd=open("%s.pub" % rsaKey, "r")
            mykey = paramiko.RSAKey.from_private_key_file(rsaKey)
        except:
            raise
            cmd="ssh-keygen -q  -t rsa -N '' -f %s" % rsaKey
            ok, code = rim.runCmd(self.log, cmd)
            try:
                fd=open("%s.pub" % rsaKey, "r")
                mykey = paramiko.RSAKey.from_private_key_file(rsaKey)
            except:
                ssh.close()
                self.log("Key generation failed : %d" % code)
                return None

        #let paramiko know where it is so that AutoAffPolicy can add any new keys to it
        ssh.load_host_keys(hostFile)

        try:
            self.log("Connecting with no password")
            ssh.connect(myXip, username=self.login, pkey=mykey)
            self.log("Successfully connected without password")
        except paramiko.AuthenticationException:
            try:
                self.log("Failed passwordless login - trying with configured password")
                ssh.connect(myXip, username=self.login, password=self.pw)
            except paramiko.AuthenticationException:
                ssh.close()
                s="Invalid password or username was supplied"
                self.log(s)
                return None
            except Exception as detail:
                ssh.close()
                s="Could not connect to '%s@%s' : %s" % (self.login, self.pw, detail)
                self.log(s)
                return None
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
                ssh.connect(myXip, username=self.login, pkey=mykey)
            except Exception as detail:
                s="Password less access failed - %s" % (detail)
                self.log(s)
                return None
        except Exception as detail:
            s="connection to '%s@%s' : %s" % (self.login, myXip, detail)
            self.log(s)
            return None

        ssh.close()        
        return True
        
    def getTelnet(self):
        # see if we already have setup a telnet port for that vm
        blobs=self.session.xenapi.VM.get_blobs(self.vmRef)
        if blobs.has_key("telnetPort"):
            bref=blobs["telnetPort"]
            bi=self.session.xenapi.blob.get_record(bref)
            self.telnet=int(bi['name_description'])
            self.log("Found xen blob data")
            return True
        else:
            # scan all blobs 
            self.log("Xen blob info not found - creating")
            brefs=self.session.xenapi.blob.get_all()
            used=[]
            for bref in brefs:
                bi=self.session.xenapi.blob.get_record(bref)
                if bi['name_label']=='telnet':
                    used.append(int(bi['name_description']))
            for port in range(self.telnetBase, self.telnetBase+200):
                if port not in used:
                    bref=self.session.xenapi.VM.create_new_blob(self.vmRef, 'telnetPort', '', True)
                    self.session.xenapi.blob.set_name_description(bref, "%d" % port)
                    self.session.xenapi.blob.set_name_label(bref, 'telnet')
                    self.telnet=port
                    return True
            self.log("Ran out of free telnet port (200 max)")
            sys.exit(1)
    
    def respawn(self, cmd):
        while True:
            self.log("Respawn - starting '%s'" % cmd)
            child = subprocess.Popen(cmd, shell=True)
        
    def start(self, debug=False):
        self.logFile=open("%s/console.%s" % (self.cdir, self.vmName), "a")
        if not debug:
            try:
                pid = os.fork()
            except OSError, e:
                raise Exception, "%s [%d]" % (e.strerror, e.errno)

            if (pid == 0):  
                os.setsid()
                try:
                    pid = os.fork()
                except OSError, e:
                    raise Exception, "%s [%d]" % (e.strerror, e.errno)
                if (pid != 0):
                    open("/var/run/console-%s.pid" % self.vmName, "w").write(str(pid))
                    os._exit(0)
            else:
                return
    
        # We are now running inside a detached child process

        # find a free telnet port
        if not self.getTelnet(): return None
        
        sel=selector.selector()
 
        telneti=telnet(self.telnet, self.logFile, None, self.vmName)
        inOuti=inOut(None, telneti)
        sel.addHandler(telneti)
        sel.addHandler(inOuti)

        while True:
        
            # wait for the vm to be in the proper state
            state=self.session.xenapi.VM.get_power_state(self.vmRef)
            self.log("%s's power state is '%s'" % (self.vmName, state))
            if state != 'Running':
                self.log("Waiting for the vm to be running. Current state is '%s'..." % state)
                count=0
                while True:
                    state=self.session.xenapi.VM.get_power_state(self.vmRef)
                    if state == 'Running': break
                    count=count+1
                    count=count%120
                    if not count:
                        self.log("%s's power state is %s , waiting for 'Running'" % (self.vmName, state))
                    time.sleep(.25)
                self.log("Vm is runing")
            # find our host
            self.myHost, domid=self.getHostAndDomain()
            self.log("host:domid is '%s:%s'" % (self.myHost, domid))
            if not domid: 
                self.log("going to sleep")
                time.sleep(.5)
                continue
                
            # set up the keys
            if not self.setKeys(self.myHost): break # FATAL
            
            # fireup the server side 
            cmd="socat UNIX-LISTEN:%s SYSTEM:'ssh -t %s@%s /usr/lib/xen/bin/xenconsole %s',pty" % (self.unixFile, self.login, self.myHost, domid)
            child = subprocess.Popen(cmd, shell=True)
            self.log("Started socat as '%s'" % child)
            us = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            # wait for the socket file to be created
            self.log("Waiting for unix socket file %s" % self.unixFile)
            while True:
                try:
                    us.connect(self.unixFile)
                    break
                except:
                    time.sleep(.5)
            self.log("Unix socket file %s is connected" % self.unixFile)
            telneti.addUs(us)
            inOuti.addUs(us)
            self.log("Entering waitloop")
            sel.waitLoop()
            self.log("Waitloop exited")
            code=child.wait()
            # something happened to the 
            self.log("Child exited with %d" % code)
            # give the xenserver environment time to react and update vm power state
            time.sleep(4)
        
if __name__ == '__main__':
    c=Console('Server')
    c.start(debug=True)
