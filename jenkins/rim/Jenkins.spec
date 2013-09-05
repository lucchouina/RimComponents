<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Jenkins-1.517" version="1.0" flags="required" fs="squashfs" level="2" >
        
        <requires name="tomcat7"/>
        <requires name="dfw"/>
        <requires name="python2.6"/>
        <requires name="perl-5.8.7" />
        <requires name="avahi-server"/>
        
        <element source="jenkins.war" target="/var/lib/tomcat${jenkinsTomcatVer}/webapps/ROOT.war"/>
        
        <!-- drop a logo in the proper place for initmode interface to use -->
        <element source="jenkins.png" target="/etc/productlogo.png" />
        <element source="favicon.ico" target="/favicon.ico" />
     
        <script context="postinstall" rank="35">
            <![CDATA[
                echo "CATALINA_OPTS='-DJENKINS_HOME=${jenkinsHome}'" >> /etc/default/tomcat${jenkinsTomcatVer}
                #
                # setup port 
                #
                echo '{"HttpInfo":{"Port":'${tomcatPort}'}}' | setSystemInfo -n > /dev/null
                #
                # must put an invalid entry in firewall file to prime the setSystemInfo 
                #
                echo "tcp ${tomcatPort} ACCEPT" > /etc/firewall.d/tomcat    
                #
                mkdir -p /$rimPubData/jenkins
                ln -s /$rimPubData/jenkins ${jenkinsHome}
                echo "/$rimPubData/jenkins true" > /etc/backups/jenkins
                chown -R ${tomcatRunTimeUserId}:${tomcatRunTimeGroupId} /$rimPubData/jenkins
             ]]>
        </script>
        <script context="prerestore" rank="36">
            <![CDATA[
                /etc/init.d/tomcat7 stop
                return 0
             ]]>
        </script>
        <script context="postrestore" rank="36">
            <![CDATA[
                /etc/init.d/tomcat7 start
                return 0
             ]]>
        </script>
     </module>
</spec>
