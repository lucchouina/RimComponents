<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Git-client-1.7.0.4" version="1.0" flags="required" level="5" fs="squashfs">
        
        <element source="/etc/bash_completion.d/git" />
        <element source="/var/cache/git" type="emptydir" />
        <element source="/usr/share/git-core/templates" type="dir" recurse="1" mask="*"/>
        <element source="/usr/lib/git-core" type="dir" recurse="1" mask="*"/>
        <element source="/usr/share/git-core" type="dir" recurse="1" mask="*"/>
        <element source="/usr/bin" target="/bin" type="dir" recurse="1" mask="git[.]*" shadow="1"/>
                
    </module>
</spec>
