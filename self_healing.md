**Eidolon**
=========

Eidolon is a service which acts as a plugin to repmgr, allowing the Postgres and Repmgr services to be ennabled, with a failed primary being re-added to the cluster as a standby automatically.
There are no official releases; this project exists purely as a template and might require some finetuning per environment. For examples, see [Important Information](#important-information)

For installation instructions skip to [Installation](#installation).

Overview
--------

Eidolon consists of two files, a bash script called `eidolon.sh` and a `repmgr.service` which uses it.

Automatic rejoin
----------------

It is possible to use [primgr](https://gitlab.com/pg_pantheon/primgr) to facilitate self healing to a certain degree by enabling the postgres and repmgr services.
When the repmgr service starts, it can run a script which checks primgr, and if the primary reported by primgr is different than the node which failed, we assume a failover ocurred. Then, the script can perform a `node rejoin` or `standby clone` from the new primary, the  using information received from primgr.
In the `src` directory, you can find an example of a bash script which does this, and a repmgr service file which uses the bash script.

Requirements
------------
[primgr](https://gitlab.com/pg_pantheon/primgr)


Installation
------------

Put the bash script `src/eidolon.sh` in `/opt/eidolon.sh`.  
You can put the repmgr.service in any place your OS allows. I use `/etc/systemd/system/repmgr-{{ pg_version }}.service`

If you prefer Ansible for your deployment, you can use the playbooks and role in the [Ansible](https://gitlab.com/pg_pantheon/ansible) project in the Pantheon group.

See the ansible playbook file `Ansible/playbooks/playbook_to_deploy_to_existing.yml`

Important information
---------------------

* In my environment all DB nodes are numbered in the DNS. For example db-node-1.com, db-node-2.com. So, the `pg_enable.sh` I use builds a list of nodes accordingly.
