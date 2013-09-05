<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Builder" version="1.0" flags="required" fs="squashfs" level="2" >
        
        <element source="/usr/bin/unzip" />
        <element source="/usr/bin/xargs" />
        <element source="/usr/bin/socat" />
        <element source="/etc/rimbootstrap" />
        <element source="/etc/settings" target="/sbin/settings/handlers/ci.py" />
        <element source="/sbin" type="dir" mask="*" recurse="1" />
        <script context="postinstall" rank="52">
            <![CDATA[
                mkdir -p /${rimPubData}/consoles
                chmod 777 /${rimPubData}/consoles
                return 0
             ]]>
        </script>
     </module>
</spec>
