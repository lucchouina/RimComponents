<?xml version="1.0" ?>
<spec version="1.0">
    <module name="JavaSE-6.31-Jdk" version="1.0" flags="required" level="5" fs="squashfs">

        <!-- This is all Rim based and downloaded from 
            http://www.oracle.com/technetwork/java/javase/downloads/index.html
            www.oracle.com/technetwork/java/javase/downloads/index.html
         -->

        <!-- Grab everything for now -->
        <element source="." target="${T_JavaRoot}" type="dir" mask="*" recurse="1" />
        
        <script context="postinstall" rank="48">
            <![CDATA[
                # add the java tools location to the global PATH
                if ! grep -q ${T_JavaRoot}/bin /etc/profile; then echo "export PATH=\$PATH:${s2Root}/bin" >> /etc/profile; fi
                return 0
             ]]>
        </script>
    </module>
</spec>
