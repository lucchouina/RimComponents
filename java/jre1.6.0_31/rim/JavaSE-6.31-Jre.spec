<?xml version="1.0" ?>
<spec version="1.0">
    <module name="JavaSE-6.31-Jre" version="1.0" flags="required" level="5" fs="squashfs">

        <!-- This is all Rim based and downloaded from 
            http://www.oracle.com/technetwork/java/javase/downloads/index.html
            www.oracle.com/technetwork/java/javase/downloads/index.html
         -->
         
        <!-- Must be .../jre fort libraries load to work properly without LD_LIBRARY_PATH -->
        <var name="T_JreRoot" value="${T_JavaRoot}/jre"/>
        
        <element source="${T_JreRoot}/bin/java" target="/usr/bin/java" type="link" />
        
        <!-- Tomcat, for one, will be looking for this jre directory -->
        <element source="jre" target="${T_JavaRoot}/java-6-sun" type="link" />
        
        <element source="lib" target="${T_JreRoot}/lib" type="dir" mask="*" recurse="1" />
        <element source="bin" target="${T_JreRoot}/bin" type="dir" mask="*" recurse="1" />
        <element source="javaws" target="${T_JreRoot}/javaws" type="dir" mask="*" recurse="1" />
        <element source="plugin" target="${T_JreRoot}/plugins" type="dir" mask="*" recurse="1" />
        
        <script context="postinstall" rank="49">
            <![CDATA[
                return 0
             ]]>
        </script>
    </module>
</spec>
