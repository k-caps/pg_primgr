#!/bin/bash

lockfile=/var/run/postgresql/.pg_enable.lock
log=/var/log/pgsql/autostart_errors.log
primgr_port=5999
pg_version=12
start_number_of_servers=1
end_number_of_servers=3
PGDATA=/var/lib/pgsql/$pg_version/data
CONF_FILES=("$PGDATA/postgresql.conf" "$PGDATA/pg_hba.conf" "$PGDATA/server.crt" "$PGDATA/server.key")
fdate() { date "+%d-%m-%Y %H:%M:%S" "$@"; }
printf "$(fdate) - [INFO] - PG Autostart script started.\n" >> $log

# Copies all files to /tmp in order to prevent files transfered empty
cp -f --copy-contents $CONF_FILES /tmp/
chmod 400 /tmp/server.key

if [[ -e $lockfile ]]; then
                printf "$(fdate) - [INFO] - Enable postgres job already running.\n" >> $log
                exit
else
    touch $lockfile
    
    # Building a list of all servers that are in the same site as the current node
    NODES=""
    for (( index=$start_number_of_servers; index<=$end_number_of_servers; index++))
    do
        NODES="${NODES}$(echo $(hostname) | sed 's/[1-3]/'${index}'/') "
    done

    # If a cluster is healthy: Check if it is needed to perform actions to rejoin the failed node back to the cluster (rejoin / clone),
    # it means that the current node just thinks that he is alone in the cluster and needs to be rejoined to the cluster, or cloned by 'standby clone'.
    for nd in $NODES
    do
         # Checking other nodes that are not me are available
         if [ "$nd" != "$(hostname)" ]; then
             # Check $nd and see if the node is available using primgr
             if [[ $(curl --silent $nd:$primgr_port/state | grep 'Primary') ]] ||
                [[ $(curl --silent $nd:$primgr_port/state | grep 'Standby') ]]; then
                     printf "$(fdate) - [INFO] - $nd is reachable.\n" >> $log
                     # Find the current actual master
                     if [[ $(curl --silent $nd:$primgr_port/state | grep 'Primary') ]]; then
                        actual_master=$nd
                        printf "$(fdate) - [INFO] - $nd is set to actual primary.\n" >> $log
                     fi
             else
		     printf "$(fdate) - [WARNING] - Unable to reach primgr in server ' $nd ', server is unreachable, cluster is unhealthy.\n" >> $log
                     rm $lockfile
                     exit
             fi
         fi
    done

    # Check if a rejoin / clone is nececssary on those who arent actual master (IE don't do this on the actual master)
    if [ "$actual_master" != "$(hostname)" ]; then
        nd=$(echo $(hostname))
        printf "$(fdate) - [INFO] - This node $nd is not the reported master.\n" >> $log
        # check if this node thinks that it is running as master
        if [[ $(curl --silent $nd:$primgr_port/master | grep $nd) ]]; then
              printf "$(fdate) - [INFO] - This node $nd thinks it is the master \n" >> $log
              # check if theres an upstream warning - this sed command checks whether that line exists in the output
              if [[ $(/usr/pgsql-$pg_version/bin/repmgr -f /etc/repmgr/$pg_version/repmgr.conf cluster show 2>&1 | sed -e '/registered as standby but running as primary/,/reports a different upstream/!d') ]]; then
                        # rejoin to the reported master
                        printf "$(fdate) - [INFO] - Attempting to node rejoin from $actual_master.\n" >> $log
                        sudo systemctl stop postgresql-$pg_version
                        /usr/pgsql-$pg_version/bin/repmgr -f /etc/repmgr/$pg_version/repmgr.conf node rejoin -d "host=$actual_master dbname=repmgr user=repmgr" --force-rewind --config-files=postgresql.conf,pg_hba.conf,server.crt,server.key
                        rc=$?

                        # if node rejoin failed try a standby clone
                        if [[ $rc != 0 ]]; then
                              printf "$(fdate) - [ERROR] - node rejoin from $actual_master failed, will attempt standby clone.\n" >> $log
                              printf "$(fdate) - [INFO] - Attempting standby clone from $actual_master.\n" >> $log
                              rm -rf /var/lib/pgsql/$pg_version/data
			      rm -rf /temp_tbs/*
                              /usr/pgsql-$pg_version/bin/repmgr -f /etc/repmgr/$pg_version/repmgr.conf standby clone -h $actual_master -U repmgr -d repmgr -F --fast-checkpoint
                              cp -f /tmp/{postgresql.conf,pg_hba.conf,server.crt,server.key} /var/lib/pgsql/$pg_version/data/
                              sudo systemctl restart postgresql-$pg_version
                              /usr/pgsql-$pg_version/bin/repmgr -f /etc/repmgr/$pg_version/repmgr.conf standby register --force
                              printf "$(fdate) - [INFO] - standby clone from $actual_master finished.\n" >> $log

                        # node rejoin succeded
                        else 
                            printf "$(fdate) - [INFO] - node rejoin from $actual_master finished.\n" >> $log
                        fi
              fi
        fi
        # Delete inactive barman slot to prevent pg_wal spamming
        if [[ $(/usr/pgsql-$pg_version/bin/psql -U postgres -d repmgr -t -c "SELECT * from pg_replication_slots;" | grep 'barman' | awk -F '|' '{print$1$7}' | xargs) == 'barman f' ]]; then
            /usr/pgsql-$pg_version/bin/psql -U postgres -d repmgr -t -c "SELECT * from pg_drop_replication_slot('barman');" 2>/dev/null
            printf "$(fdate) - [INFO] - dropped barman replication slot\n" >> $log
        fi
    fi
    rm $lockfile
fi