<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Dev" version="1.0" flags="required" fs="squashfs" level="4" >
        <element source="/usr/bin/nedit" />
        <element source="/usr/bin/nc" />
        <element source="/usr/bin/xauth" />
        <element source="/usr/share/X11" type="dir" recurse="1" mask="*" />
        <element source="/etc/X11" type="dir" recurse="1" mask="*" />
     </module>
</spec>
