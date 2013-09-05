<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Tomcat7_7.0.21" version="1.0" flags="required" level="7" fs="squashfs" >

        <!-- All root based for now - so update your root with the following packages:
            tomcat7
            tomcat7-common
            libtomcat7-java
            libservlet3.0-java
            libcommons-pool-java
        -->
        
        <!-- Note: be two vars should match against init.d/tomcat7 environment veriables -->
        <var name="HOME" value="/usr/share/tomcat7"/>
        <var name="BASE" value="/var/lib/tomcat7"/>

        <element source="/etc/tomcat7" type="dir" mask="*" recurse="1" />
        <element source="/etc/default/tomcat7" />
        <element source="/var/lib/tomcat7" type="dir" mask="*" recurse="1" />
        <element source="/usr/share/tomcat7" type="dir" mask="*" recurse="1" />
        <element source="/etc/logrotate.d/tomcat7" />
        <element source="/etc/cron.daily/tomcat7" />
        <element target="/var/log/tomcat7" type="emptydir" owner="${tomcatRunTimeUserId}" group="${tomcatRunTimeGroupId}" />
        <element target="/var/cache/tomcat7" type="emptydir" owner="${tomcatRunTimeUserId}" group="${tomcatRunTimeGroupId}" />
        
        <element source="/usr/share/java" type="dir" mask="tomcat-.*" recurse="1" />
        <element source="/usr/share/java" type="dir" mask="catalina-.*" recurse="1" />
        <element source="/usr/share/java" type="dir" mask="commons-.*" recurse="1" />
        <element source="/usr/share/java/ecj.jar" />
        
        <!-- by default we send everything to syslog subsystem, so drop the extra jars that
             support this service in the global area LIB for all to use -->
        <element source="extras/tomcat-juli-adapters.jar" target="/usr/share/java/tomcat-juli-adapters.jar" />
        <element source="extras/tomcat-juli.jar" target="/usr/share/java/tomcat-juli.jar" />
        <element source="extras/log4j.jar" target="/usr/share/java/log4j.jar" />
        <element source="../../java/log4j.jar" target="${HOME}/lib/log4j.jar" type="link"/>
        <element source="../../java/tomcat-juli-adapters.jar" target="${HOME}/lib/tomcat-juli-adapters.jar" type="link"/>
        <element source="../../java/tomcat-juli.jar" target="${HOME}/bin/tomcat-juli.jar" type="link"/>
        
        <!-- Drop a log4j config file that defines and sends to SYSLOG -->
        <element source="extras/log4j.properties" target="${HOME}/lib/log4j.properties" />
        
        <!-- init rc -->
        <var name="initScript" value="tomcat7" />
        <element source="/etc/init.d/${initScript}" />
        
        <!-- settings handler -->
        <element source="settings" target="/sbin/settings/handlers/web.py" />
        
        <script context="postinstall" rank="50">
            <![CDATA[
                groupadd -f -o -g ${tomcatGid} tomcat7
                egrep -q "^tomcat7:" /etc/passwd || (
                    useradd -M \
                        -s /bin/bash \
                        -u ${tomcatUid} \
                        -g ${tomcatGid} \
                        -c "Tomcat runtime user name" \
                        -d /usr/share/tomcat7 \
                        tomcat7
                ) 2>/dev/null 1>&2
                chown -RL ${tomcatRunTimeUser}:${tomcatRunTimeGroup} /var/lib/tomcat7
                return 0
             ]]>
        </script>
        <script context="prerestore" rank="2">
            <![CDATA[
                service tomcat7 stop
                return 0
             ]]>
        </script>
        <script context="postrestore" rank="9">
            <![CDATA[
                service tomcat7 start
                return 0
             ]]>
        </script>
    </module>
</spec>
