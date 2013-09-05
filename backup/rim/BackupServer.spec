<?xml version="1.0" ?>
<spec version="1.0">
    <module name="BackupServer" version="1.0" flags="required" level="4" fs="squashfs">
        <!-- in the above, 117:123 is postgres:postgres -->
        <requires name="dfw"/>
        <requires name="avahi-server"/>
        <element source="/etc/issue" />
        <script context="postinstall" rank="35">
            <![CDATA[
                return 0
             ]]>
        </script>
        <script context="firstbootpredb" rank="35">
            <![CDATA[
                return 0
             ]]>
        </script>
    </module>
</spec>
