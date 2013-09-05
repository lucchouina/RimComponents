<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Postgres-9.2" version="2.0" flags="required" level="5" fs="squashfs" owner="${postgresUid}" group="${postgresGid}">

        <requires name="Postgres_common" />
        <!-- Refer to postgresql 9.1l spec file for list of packages that need to be installed -->

        <element source="/usr/lib/postgresql/9.2" type="dir" mask="*" recurse="1" />
        <element source="/usr/share/postgresql/9.2" type="dir" mask="*" recurse="1" />
        
        <!-- we removed these files from the root to eliminate dups -->
        <element source="/etc/postgresql.conf" />
        <element source="/etc/pg_hba.conf"  />
        <element source="/usr/share/postgresql/9.2" type="dir" mask="*" recurse="1" />
        <element source="/var/log/postgresql" type="emptydir" />
        
        <script context="postinstall" rank="35">
            <![CDATA[
                #
                # firstboot will need the name of the previous running version 
                # in order to perform the db upgrade.
                #
                if [ ! "$reset" -a ! -d /curroot/var/lib/postgresql/9.2 ]
                then
                    # force a move of the newly installed 9.2 init db to /data
                    rm -f /var/lib/postgresql/oldDbDir
                fi
                if [ ! -d /var/lib/postgresql/9.2 ]
                then
                    #
                    # create the initial cluster
                    echo -n "Creating database..."
                    pg_createcluster -u postgres -e UTF8  --lc-collate=en_US.utf8 --lc-ctype=en_US.utf8 9.2 main > /var/log/dbcreate.log
                    echo "Done - $?"
                fi
                return 0
             ]]>
        </script>
    </module>
</spec>
