<?xml version="1.0" ?>
<spec version="1.0">
    <module name="prof" version="1.0" flags="required" level="9" fs="squashfs">
        
        <element source="/usr/share/file" type="dir" recurse="1" mask="*" />
        <element source="/usr/bin/lsof" />
        <element source="/bin/fuser" />
        <element source="/usr/bin/ldd" />
        
        <!-- for support of threads in gdb -->
        <element source="/usr/bin/gdbserver" />
        <element source="/usr/bin/gdb" />
                
        <!-- resource tracking -->
        <element source="track/initrc" target="/etc/init.d/trx"/>
        <element source="track/settings" target="/sbin/settings/handlers/track.py"/>
        <element source="track/libtrx.so" target="/lib/trx.so" />
        <element source="track/trxmgr" target="/sbin/trxmgr"/>

        <!--
            Test guys want these - START
            FIXME - need to create a test module which does not ship
        -->
        <element source="/usr/sbin/tcpdump" />
        <element source="/usr/bin/nslookup" />
        <element source="/usr/bin/sftp" />
        <element source="/usr/bin/ftp" />
        <element source="/usr/lib/openssh/sftp-server" target="/usr/lib/sftp-server" />
        <!--
            Test guys want these - END
        -->
   </module>
</spec>
