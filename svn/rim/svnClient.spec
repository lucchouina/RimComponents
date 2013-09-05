<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Svn-client-1.7.9" version="1.0" flags="required" level="5" fs="squashfs">
        <element source="/lib" type="dir" recurse="0" mask="libsvn_[.]*"/>
        <element source="/lib" type="dir" recurse="0" mask="libneon_[.]*"/>
        <element source="/bin" type="dir" recurse="0" mask="svn[.]*"/>
        <element source="/bin/neon-config"/>
    </module>
</spec>
