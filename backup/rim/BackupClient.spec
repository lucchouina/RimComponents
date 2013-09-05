<?xml version="1.0" ?>
<spec version="1.0">
    <module name="BackupClient" version="1.0" flags="required" level="4" fs="squashfs">
        <requires name="iscsi-2.0"/>
        <element source="/etc/backups.conf" /> 
        <element source="/etc/logrotate.d/backups" /> 
        <element source="/etc/cron.d/backups.cron" target="/etc/cron.d/backups"/> 
        <element source="/etc/backups/system" /> 
        <element source="/sbin/run-backups" /> 
        <element source="/sbin/run-recover" /> 
        <element source="/sbin/check-recover" /> 
        <element source="/sbin/recover" /> 
        <element source="/sbin/stop-backups" /> 
        <element source="/sbin/backups.py" /> 
        <element source="/sbin/transports" target="/sbin/transports" type="dir" recurse="1" mask="*" />
        <element source="/sbin/listBackups" /> 
        <element source="/sbin/recoverWal" /> 
        <element source="/sbin/archiver" /> 
        <element source="/sbin/onBackup" /> 
        <element source="/sbin/testBackups" /> 
        <element source="/sbin/mount.cifs" /> 
        <element source="/sbin/settings.py" target="/sbin/settings/handlers/backup.py" /> 
        <element source="/sbin/reccfg.py" target="/sbin/settings/handlers/recovery.py" /> 
        <script context="postinstall" rank="36">
            <![CDATA[
                echo 'postgres ALL=(root) NOPASSWD: /sbin/archiver' > /etc/sudoers.d/postgres
                echo 'postgres ALL=(root) NOPASSWD: /sbin/run-backups' >> /etc/sudoers.d/postgres
                chmod 0440 /etc/sudoers.d/postgres
                #
                # save root ssh keys we use for remote backups
                #
                cp -r /curroot/root/.ssh /root 2>/dev/null
                #
                # create a unique iscsi initiator name
                mac=`ifconfig eth0 | sed -n -e 's/://g' -e 's/.*HWaddr *\([0-9a-z]*\)/\1/p'`
                echo InitiatorName=iqn.2013-05.com.rimsys:01:$mac > /etc/iscsi/initiatorname.iscsi
                return 0
             ]]>
        </script>
        <script context="firstbootpredb" rank="36">
            <![CDATA[
                return 0
             ]]>
        </script>
        <script context="prebackup" rank="0">
            <![CDATA[
                return 0
             ]]>
        </script>
        <script context="postbackup" rank="0">
            <![CDATA[
                return 0
             ]]>
        </script>
        <script context="prerestore" rank="0">
            <![CDATA[
                return 0
             ]]>
        </script>
        <script context="postrestore" rank="0">
            <![CDATA[
                return 0
             ]]>
        </script>
    </module>
</spec>
