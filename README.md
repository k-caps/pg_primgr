**The Postgres Primary Manager - pg_primgr**
=========
primgr is a service which acts as an extension to repmgr, exposing a port which returns the current state of each node in the cluster.  
This allows any load balancer to dynamically route traffic to the current DB primary, as well as other potential applications such as self healing. For more information, see the [self healing section](#self-healing).  
Due to the highly configurable nature of Postgres replication, it is unlikely that a "one size fits all" configuration would work. The official release attempts sane, generic defaults, but might require some fine-tuning for more specific environments or configurations. For examples, see [Important Information](#important-information).

For installation instructions skip to [Installation](#installation).

Overview
--------

The core of primgr is a python 3.6 webserver, located in `/opt/primgr` on each Postgres server, which uses FastAPI to expose a few endpoints that are used to determine the state of the local DB instance in relation to the both itself and the rest of the cluster. The program checks the `repmgr.nodes` table in the local instance of PostgreSQL, and returns an HTTP status code which can be used by haproxy or any other load balancing software, or any other application which needs reliable information on the state of the cluster, such as monitoring orautomations.
The API is based on the following logic flow, the code "asking" and then acting based on the answers:  
- Is the DB up? 
- If so, is it in recovery mode (this means it is a standby)? 
- If not, do the other nodes in the cluster also think that I am the primary? 

Requirements:
-------------
See the requirements section in the [API documentation](docs/primgr_api.md).

Installation
------------
You can use the RPMs from the releases page, or adapt and run any of the methods provided in the `install_scripts` directory, or manually, by placing the files in thier respective locations..

### RPM installation
Download the RPM files you want to use and install them on the relevant machines - `primgr.rpm` and `primgr-pg-autostart.rpm` should be installed on all Postgres nodes, and `primgr-haproxy.rpm` on all haproxy node.

**`primgr.rpm`** installs only the core API on the assumption that you know how you want to use it.  
**`primgr-pg-autostart.rpm`** changes the systemctl script for Postgres, enabling it and adding a bash script that checks the cluster at node startup. If a node is running as primary, but is not recognized as a primary, it will determine the current acting primary and attach itself as a standby automatically. This is of course only useful in case of the node or service actually going down, and cannot automatically heal network splits. This is planned for future releases.  
**`primgr-haproxy.rpm`** configures an `haproxy.cfg` to automatically send new connections to the actual primary only. You will need to add your own hostnames to `haproxy.cfg` after it has been installed.  


### Script installation
If you require more fine-tuning than the RPMs provide, you can use the provided bash installation scripts as a reference or attempt to use them as-is. They do exactly the same as the RPMs, however you control all aspects instead of trusting the RPM.

If you prefer Ansible for your deployment, you can use the provided playbooks and role, which also configures haproxy. You will need to populate your own inventory. 
See the ansible playbook file `install_scripts/ansible/playbooks/playbook_to_deploy_to_existing.yml` to get started

### Manual installation
If you choose a manual install, you will need to deploy the files in the `src` directory manually, in whatever directory structure you like.    
You will have to put the haproxy configuration in your haproxy.cfg, or simply use it as a reference for the load balancer of your choice.  

For primgr itself, the suggested layout is:  
```
/opt/primgr/
  main.py
  repmgr_node.py
```

The file `primgr.py` should be renamed to `main.py`.  

You will also need to configure your system to restart primgr if it crashes.  
You can use the `primgr.service.j2` file as an example systemd resource.  


Important information
---------------------

* Note that in the python source, `-` is replaced by `_` in some cases. This is because my installation of repmgr uses `<server_name.com>` instead of `<server-name.com>` in its configurations. If this is not wanted, you need to use the Script installation and change this to suit your environment.   

* The current implementation only polls nodes in the same `location` (repmgr metadata). If you aren't using locations, you need to change the code in `get_all_other_nodes_in_site()` and the calling `get_node_site()` under `get_state()`.

* In my environments, all DB nodes are numbered by DNS. For example db-node-1.com, db-node-2.com. So, the `pg_autostart.sh` included here use builds a list of nodes accordingly.

Self healing
------------
It is possible to use primgr to facilitate self healing to a certain degree by enabling the postgres and repmgr services.
When the repmgr service starts, it can run a script which checks primgr, and if the primary reported by primgr is different than the node which failed (localhost), we assume a failover ocurred. Then, the script can perform a `node rejoin` or `standby clone` from the new primary, using information received from primgr.
In the `src/autostart` directory, you can find an example of a bash script which does this, and a repmgr service file which uses the bash script.
