<?xml version="1.0" ?>
<spec version="1.0">
    <module name="rim" version="1.0" flags="required" level="3" fs="squashfs">
        
        <!-- for bleater support on dev boxes -->
        <element source="/usr/bin/beep" arch="i386 x86_64" />
		
        <!-- Start with NewYork time -->
        <element source="/etc/timezone" />
        <element source="/etc/localtime" />
        
        <element target="/var/log/rim" type="emptydir" owner="${rimUserUid}" />
        
        <!-- common rim sudoers config -->
        <element source="etc/sudoers" target="/etc/sudoers.d/rimcommon" perm="440" owner="0" group="0" />
        
        <element source="/sbin/sudoadminconsole"/>
        
        <script context="postinstall" rank="32">
            <![CDATA[
                #
                # create the users and groups
                #
                mkdir -p /${rimPubData}/home/${rimSupportName}
                mkdir -p /${rimPubData}/home/${rimUserName}
                #
                # Account creation
                #
                unspokenpwd='$6$PvFOiGLH$0YtMS/jxBveoABWcpKSuELVzQQY8olNNFOk1lu3Z8R57awXWBFYmx3DfelvKHQ1D9a2OZgP2czUw15PPaXdcP1'
                manufPwd='$6$5ohOLTPC$wCZD2f5BluL6WzMdiQxYfTFT9.r798NYuIZPVYaSY6OETksKuQ.dV51GEyfhPjxaw2hyGMtUNJyz3uk1QeEkH/'
                adminPwd='$6$BZXytq.F$SlTsMuN1NaWWGaYl4485RjwTahG7hnkT5Fl.sXQQNa8LSkCEL9G6CpP/homtarTVoz8zRMWvcKRr5Vh6F6yxH/'
                adminConsole=${rimRoot}/bin/adminconsole
                if [ "$rimProduct" == M1Manuf ]
                then
                    unspokenpwd=$manufPwd
                elif [ "${rimProduct}" == Global ]
                then
                    adminConsole=/sbin/sudoadminconsole
                fi
                groupadd -f -o -g ${rimUserGid} ${rimUserName}
                groupadd -f -o -g ${rimSupportGid} ${rimSupportName}
                egrep -q "^${rimSupportName}:" /etc/passwd || (
                    useradd -m \
                        -s /bin/bash \
                        -u ${rimSupportUid} \
                        -g ${rimSupportName} \
                        --password $unspokenpwd \
                        -c "rim support team access" \
                        -d /home/${rimSupportName} \
                        -G admin,adm \
                        ${rimSupportName}
                )  2>/dev/null 1>&2
                egrep -q "^${rimUserName}:" /etc/passwd || (
                    useradd -M \
                        -s /bin/sh \
                        -u ${rimUserUid} \
                        -g ${rimUserName} \
                        --password $unspokenpwd \
                        -c "rim runtime and adminconsole" \
                        -d /home/${rimUserName} \
                        ${rimUserName}
                )  2>/dev/null 1>&2
                egrep -q "^${rimAdminName}:" /etc/passwd || (
                    useradd -M \
                        -u ${rimAdminUid} \
                        -g ${rimUserName} \
                        -c "rim admin config utility" \
                        --home "/" --no-create-home \
                        --shell ${adminConsole} \
                        --password ${adminPwd} \
                        ${rimAdminName}
                ) 2>/dev/null 1>&2
                
                #
                # log 
                #
                mv /var/log /var/log.saved
                mkdir -p /${rimPubData}/var/log
                ln -s /${rimPubData}/var/log /var/log
                ((cd /var/log.saved && tar cf - .) | (cd /var/log && tar xBf -)) 2>/dev/null 1>&2
                \rm -rf /var/log.saved
                mkdir -p /var/log/rim
                touch /var/log/rim/messages
                chown ${rimUser}:${rimUser} /var/log/rim
                chown ${rimUser}:${rimUser} /var/log/rim/messages
                chmod 777 /var/log/rim
                chmod 777 /var/log/rim/messages
                touch /var/log/syslog
                chmod 777 /var/log/syslog

                #
                # set PATH
                #
                (
                    grep ${rimRoot}/bin /home/${rimSupportName}/.bash_profile 2>/dev/null 1>&2 || echo "export PATH=\$PATH:${rimRoot}/bin"
                    grep ${rimRoot}/scripts /home/${rimSupportName}/.bash_profile 2>/dev/null 1>&2 || echo "export PATH=\$PATH:${rimRoot}/scripts"
                    
                ) | tee -a /home/${rimUserName}/.bash_profile >> /home/${rimSupportName}/.bash_profile
                (
                    grep ${rimRoot}/bin /home/${rimSupportName}/.bashrc 2>/dev/null 1>&2 || echo "export PATH=\$PATH:${rimRoot}/bin"
                    grep ${rimRoot}/scripts /home/${rimSupportName}/.bashrc 2>/dev/null 1>&2 || echo "export PATH=\$PATH:${rimRoot}/scripts"
                    
                ) | tee -a /home/${rimUserName}/.bashrc >> /home/${rimSupportName}/.bashrc
                chown -R  ${rimSupportName}:${rimSupportName} /${rimPubData}/home/${rimSupportName}
                chown -R  ${rimUserName}:${rimUserName} /${rimPubData}/home/${rimUserName}
             ]]>
        </script>
    </module>
</spec>
