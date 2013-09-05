<?xml version="1.0" ?>
<spec version="1.0">
    <module name="Lxc-0.8.0" version="1.0" flags="required" level="5" fs="squashfs">
    
        
        <element source="conf/containers.initrc" target="/etc/init.d/containers" />

        <!--  linux containers support. Requires a container enabled kernel -->
        <element source="/bin/lxc-cgroup"/>
        <element source="/bin/lxc-checkconfig"/>
        <element source="/bin/lxc-console"/>
        <element source="/bin/lxc-create"/>
        <element source="/bin/lxc-destroy"/>
        <element source="/bin/lxc-execute"/>
        <element source="/bin/lxc-freeze"/>
        <element source="/bin/lxc-kill"/>
        <element source="/bin/lxc-info"/>
        <element source="/bin/lxc-ls"/>
        <element source="/bin/lxc-monitor"/>
        <element source="/bin/lxc-netstat"/>
        <element source="/bin/lxc-ps"/>
        <element source="/bin/lxc-restart"/>
        <element source="/bin/lxc-shutdown"/>
        <element source="/bin/lxc-start"/>
        <element source="/bin/lxc-stop"/>
        <element source="/bin/lxc-unfreeze"/>
        <element source="/bin/lxc-unshare"/>
        <element source="/bin/lxc-version"/>
        <element source="/libexec" type="dir" recurse="1" mask="*"/>
        
        <!-- custom support for containers based on rim deployment -->
        <element source="scripts/mkRwCache" target="/sbin/mkRwCache" />
        <element source="scripts/runall" target="/sbin/runall" />
        <element source="scripts/setupBridge" target="/sbin/setupBridge" />
        <element source="scripts/lxc.py" target="/sbin/lxc.py" />
        <element source="scripts/containers" target="/sbin/containers" />
        <element source="scripts/settings.py" target="/sbin/settings/handlers/containers.py" />
        
        <!-- templates used for the creation of containers -->
        <element source="/conf/lxc.conf.tpl" target="/etc/lxc.conf.tpl"/>
        <element source="/conf/fstab.tpl"  target="/etc//fstab.tpl" />
        <element source="/conf/containers.conf"  target="/etc//containers.conf" />
        
        <!-- things we need fro lxc-start to work -->
        <element source="/dev/pts" type="emptydir" />
        <element source="/dev/shm" type="emptydir" />
        <element source="/usr/local/lib/lxc/rootfs" type="emptydir" />

        <!-- bridge work needed for bridging the containers to real NIC -->
        <element source="/usr/sbin/brctl" version="lts10.04"/>
        <element source="/sbin/brctl" version="lts12.04"/>
        
        <!-- all level webServer override -->
        <element source="scripts/initmode8" target="/etc/init.d/initmode8" />
        
        <!-- Logo for presentation purpose -->
        <element source="conf/lxc.png" target="/etc/lxc.png" />
        
        <!-- utilities needed for lxc -->
        <element source="/usr/bin/getopt"/>
        <element source="/bin/zgrep" />
        <element source="/var/lib/lxc" type="emptydir"/>
        
        <script context="postinstall" rank="43">
            <![CDATA[
              # add normal /sbin path to python 
              grep -q PYTHONPATH /etc/profile | grep -q /sbin || ( echo "export PYTHONPATH=$PYTHONPATH:/sbin" >> /etc/profile)
              return 0
             ]]>
        </script>
        <script context="lxcsetup" rank="10">
            <![CDATA[
              # early execution of container setup 
              lxcRoot=$1
              lxcName=$2
              if ! [ -d /${rimPubData}/$lxcName ] || ! [ -d ${lxcRoot}/${rimPivot}/${rimPubData} ]
              then
                  mkdir -p ${lxcRoot}/${rimPivot}/${rimPubData} ${lxcRoot}/${rimPivot}/${rimPubSoft}
                  # remount read only soft partition
                  grep -q ${lxcRoot}/${rimPivot}/${rimPubSoft} /proc/mounts || mount -o bind /${rimPubSoft} ${lxcRoot}/${rimPivot}/${rimPubSoft} || return 1
                  # create private public ${rimPubData} for this container
                  mkdir -p /${rimPubData}/$lxcName
                  grep -q ${lxcRoot}/${rimPivot}/${rimPubData} /proc/mounts || mount -o bind /${rimPubData}/$lxcName ${lxcRoot}/${rimPivot}/${rimPubData} || return 1
                  mkdir -p  ${lxcRoot}/${rimPivot}/${rimPrivData}
                  mkdir -p ${lxcRoot}/proc
                  grep -q ${lxcRoot}/proc /proc/mounts || mount -t proc /proc ${lxcRoot}/proc
                  #
                  # disable console and serial port gettys
                  #
                  sed -i -e 's^.*ttyS0.*^^' -e 's^.*tty1.*^^' ${lxcRoot}/etc/inittab
                  echo -n "copying public data..."
                  (
                    (cd /$rimPubData && tar cf - var tmp home) | (cd ${lxcRoot}/${rimPubData} && tar xf -)
                  ) 2>/dev/null 1>&2
              else
                  mount -o bind /${rimPubSoft} ${lxcRoot}/${rimPivot}/${rimPubSoft} || return 1
                  mount -o bind /${rimPubData}/$lxcName ${lxcRoot}/${rimPivot}/${rimPubData} || return 1
                  mount -t proc /proc ${lxcRoot}/proc
              fi
              return 0
             ]]>
        </script>
        <script context="lxcsetdown" rank="90">
            <![CDATA[
              # last execution of container un-setup or setdown
              lxcRoot=$1
              lxcName=$2
              umount ${lxcRoot}/${rimPivot}/${rimPubData} || return 1
              umount ${lxcRoot}/${rimPivot}/${rimPubSoft} || return 1
              return 0
             ]]>
        </script>
        <script context="lxcstart" rank="90">
            <![CDATA[
              return 0
             ]]>
        </script>
        <script context="lxcstop" rank="10">
            <![CDATA[
              return 0
             ]]>
        </script>
        <script context="up" rank="43">
            <![CDATA[
              # cgroup mount is required for containers 
              mkdir -p /cgroup
              mount -t cgroup cgroup /cgroup 2>/dev/null
              sysctl -w vm.overcommit_ratio=400
              sysctl -w vm.overcommit_memory=1
              return 0
             ]]>
        </script>
         <script context="down" rank="43">
            <![CDATA[
              # done with containers
              umount /cgroup
              return 0
             ]]>
        </script>
       
    </module>
</spec>
