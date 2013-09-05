<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Postgres-common" version="1.0" flags="required" level="4" fs="squashfs" owner="${postgresUid}" group="${postgresGid}">
        <!-- in the above, 117:123 is postgres:postgres -->
        <var name="initScript" value="postgresql"/>

        <!-- bin -->
        <element source="/usr/share/postgresql-common" type="dir" mask="*" recurse="1" />
        <element source="/etc/postgresql-common" type="dir" mask="*" recurse="1" />
        <element source="/etc/postgresql-common/pg_upgradecluster.d/" type="emptydir" />
      
        <!-- client -->
        <element source="/usr/bin/clusterdb"/>
        <element source="/usr/bin/vacuumlo"/>
        <element source="/usr/bin/droplang"/>
        <element source="/usr/bin/createdb"/>
        <element source="/usr/bin/createuser"/>
        <element source="/usr/bin/dropdb"/>
        <element source="/usr/bin/vacuumdb"/>
        <element source="/usr/bin/dropuser"/>
        <element source="/usr/bin/reindexdb"/>
        <element source="/usr/bin/psql"/>
        <element source="/usr/bin/createlang"/>

        <!-- from the common group -->
        <element source="/usr/bin/pg_config"/>
        <element source="/usr/bin/pg_createcluster"/>
        <element source="/usr/bin/pg_ctlcluster"/>
        <element source="/usr/bin/pg_dropcluster"/>
        <element source="/usr/bin/pg_dump"/>
        <element source="/usr/bin/pg_dumpall"/>
        <element source="/usr/bin/pg_lsclusters"/>
        <element source="/usr/bin/pg_restore"/>
        <element source="/usr/bin/pg_upgradecluster"/>
        <element source="/usr/sbin/pg_updatedicts"/>

        <!-- Some empty directories -->
        <element source="/var/run/postgresql" type="emptydir" />
        <element source="/var/log/postgresql" type="emptydir" />
        
        <!-- Log rotation rules with logrotate -->
        <element source="/etc/logrotate.d/postgresql-common" />
        
        <!-- startup - classic sysv rc stuff (no upstart) -->
        <element source="/etc/init.d/postgresql" />
        
        <!-- ssl -->
        <element source="/etc/ssl/certs/ssl-cert-snakeoil.pem" />
        <element source="/etc/ssl/private/ssl-cert-snakeoil.key" />
        
        <!-- backups -->
        <element source="/etc/backups/postgresql" />
        
        <script context="postinstall" rank="34">
            <![CDATA[
                (
                    # add a group for us
                    groupadd -f -o -g ${postgresGid} ${postgresUserName}
                    # add a user for us                                                             
                    useradd -M -u ${postgresUid} -g ${postgresUserName} ${postgresUserName} -c "PostgreSQL administrator" \
                        -d /var/lib/postgresql -G ssl-cert
                ) 2>/dev/null
                # postgresql has requirements on shm
                (
	                echo "# RIM added start to tune postgresql parameters"
	                echo "kernel.shmmax=134217728"
	                echo "kernel.shmall=2097152"
	                echo "# RIM added end to tune postgresql parameters"
                ) >> /etc/sysctl.conf
                mkdir -p /var/lib/postgresql
                chown ${postgresUserName}:${postgresUserName} /var/lib/postgresql
                [ "$curRimPrivData" ] && echo "/$curRimPrivData" > /var/lib/postgresql/oldDbDir
                return 0
             ]]>
        </script>
        <script context="firstbootpredb" rank="34">
            <![CDATA[
                #
                # with global, the database cannot be shared as it is too big to have even 2 copies.
                # on the other hand we have this luxury on NetController
                # Luc
                dbTargetDir=/$rimPubData
                [ "$isPrivPostgresql" ] && dbTargetDir=/$rimPrivData
                #
                # need to copy over?
                if [ -f /var/lib/postgresql/oldDbDir ]
                then
                    if [ "$isPrivPostgresql" ]
                    then
                        oldDbDir="`cat /var/lib/postgresql/oldDbDir`"
                        ((cd $oldDbDir && tar cf - postgresql) | (cd /$rimPrivData && tar xmf -))
                    fi
                else
                    ((cd /var/lib && tar cf - postgresql) | (cd $dbTargetDir && tar xmf -))
                fi
                # remove that original copy
                mv /var/lib/postgresql /var/lib/postgresql.orig
                # point the original to the new location
                ln -s $dbTargetDir/postgresql /var/lib/postgresql
                # create the pg_stat_tmp directory
                # not sure why it does not get created
                mkdir -p /var/lib/postgresql/9.2/main/pg_stat_tmp
                chown ${postgresUserName}:${postgresUserName} /var/lib/postgresql
                chmod 0700 /var/lib/postgresql/*/main
                chmod 400 /etc/ssl/private/ssl-cert-snakeoil.key
                return 0
             ]]>
        </script>
        <script context="prebackup" rank="35">
            <![CDATA[
                #
                # the prebackup hook is called with backup lock held so there is chance
                # that we can be stopping a postgres backup that is valid
                # Really needed for edge cases where a postgres backup could be left active
                #
                label="`date +%Y_%m_%d-%H:%M.%S`"
                psql -U postgres -c "SELECT pg_stop_backup();" 2>/dev/null 1>&2
                psql -U postgres -c "SELECT pg_start_backup('$label');" || return 1
                return 0
             ]]>
        </script>
        <script context="postbackup" rank="35">
            <![CDATA[
                psql -U postgres -c "SELECT pg_stop_backup();" || return 1
                return 0
             ]]>
        </script>
        <script context="prerestore" rank="5">
            <![CDATA[
                service postgresql stop
                return 0
             ]]>
        </script>
        <script context="postrestore" rank="5">
            <![CDATA[
                chown -RL postgres:postgres /var/lib/postgresql
                # nas a problem with permissions...
                chmod 0700 /var/lib/postgresql/*/main
                echo "restore_command = 'recoverWal %p'" > "/var/lib/postgresql/*/main/recovery.conf"
                service postgresql start
                return 0
             ]]>
        </script>
    </module>
</spec>
