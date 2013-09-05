<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Imgd" version="1.0" flags="required" fs="squashfs" level="2" >
        
        <requires name="dfw"/>
        <requires name="avahi-server"/>
        <requires name="python2.6"/>
        <requires name="nfsserver-1.2.0"/>
        <requires name="perl-5.8.7" />
        
        <element source="imgd" target="/sbin/imgd"/>
        <element source="python" target="/sbin/img" type="dir" mask="*" recurse="1" />

        <!-- Startup/shutdown hook -->
        <element source="imgd.rc" target="/etc/init.d/imgd" />

        <!-- Configuration hook -->
        <element source="settings" target="/sbin/settings/handlers/imgd.py" />

        <!-- initmode image -->
        <element source="image.png" target="/etc/productlogo.png" />
        
        <!-- so that an automagic config reload can happen without a imgd restart -->
        <element source="/usr/bin/inotifywait"/>
                
        <!-- pxe loader -->
        <element source="bin/pxelinux.0" target="/netboot/pxelinux.0" />
        <element source="bin/vesamenu.c32" target="/netboot/vesamenu.c32" />
        <element source="bin/menu.c32" target="/netboot/menu.c32" />
        <element source="pxelinux.cfg" target="/netboot/pxelinux.cfg" type="dir" recurse="1" mask="*" />
    
        <script context="postinstall" rank="34">
            <![CDATA[
                (
                    # tftp
                    echo udp 69 ACCEPT
                    # dhcp
                    echo udp 67 ACCEPT
                    # portmap
                    echo tcp 111 ACCEPT
                    # nfs
                    echo tcp 2049 ACCEPT
                    # mount
                    echo tcp 892 ACCEPT
                    # syslog
                    echo udp 514 ACCEPT
                   
                ) > /etc/firewall.d/imgd
                mkdir -p /$rimPubData/isos
                chmod 777 /$rimPubData/isos
             ]]>
        </script>
    </module>
</spec>
