<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Maven2" version="1.0" flags="required" fs="squashfs" level="2" >
        <element source="/usr/share/maven2" type="dir" mask="*" recurse="1" />
        <element source="/usr/share/java" type="dir" mask="*" recurse="1" />
        <element source="/usr/bin/mvn" />
        <element source="/usr/bin/mvnDebug" />
        <element target="/etc/maven2/maven2.conf" source="/etc/m2.conf.dpkg-new" type="link" />
        <element target="/etc/maven2/settings.xml" source="/etc/settings.xml.dpkg-new" type="link" />
    </module>
</spec>
