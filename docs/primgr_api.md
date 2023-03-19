Endpoints
---------
The endpoints which are exposed via FastAPI are:  
`/primary`, which returns a single string containing a hostname, which is what that node thinks is the current primary.  
This is used so that each node only needs to connect to its own local DB and does not have to connect to other PostgreSQL instances.  
`/realPrimary`, which checks the `/state` endpoint on all nodes, and returns the one node in the cluster which returns state: primary - the actual primary.  
`/state`, which checks the questions asked above, and returns the answer as a JSON, with the key "state" and a value, which can be any of the following:    

`Down` -  when the local DB is unavailable  
`Standby` - when the local DB is up, but in recovery mode  
`Primary` - when the local DB is up, running as  primary, and recognized as primary by the majority of nodes in its own (primary) site  
`Unknown` - when the local DB is running as primary, but is not followed by a majority of the nodes in its own site

When the `/state` endpoint is accessed, it will use FastAPI to return a response status code, as well as return the JSON with the state.

HTTP status codes
-----------------
The HTTP status codes which can be returned from FastAPI are:  
* `503` - when a DB is completely inaccessible, return this to haproxy.  
* `200` - when a DB is a primary, as agreed upon by a majority of the cluster (Only in the primary site)  
* `202` - when a DB is a standby  
* `509` - when a DB thinks it is a primary but has not received enough votes from the rest of the cluster

The script does not treat `500*` codes as an error - they are simply the state of the DB, which this script checks.  
Therefore, we always use `return` and never raise an error when we get an http code. 

Code layout
-----------

There are two code files, `primgr.py` and `repmgr_node.py`.  
`primgr.py` is the main FastAPI app file, and when deployed, will be named `main.py`.  
`repmgr_node.py` is a module which contains a class definition, `Repmgr_Node`. This refers to the local instance and contains all the methods needed for FastAPI to determine the primary.  

## Functions

### These are listed in the order they are called.

- **__init__():**
  - **Description**: Runs at class initialization, which in turn runs at FastAPI startup. Opens a connection pool to the local DB.
  - **Parameters:** None
  - **Returns:** Nothing. Sets the variable `local_conn_pool`
  - **Is used by:** `FastAPI startup event`
  - **Located in file:** `repmgr_node.py`
  <br>

- **get_reported_primary():**
  - **Description**: Gets the node which a given node thinks is the primary
  - **Parameters:** `response` (FastAPI object)
  - **Returns:** JSON, containing the key "Primary" and the value <node name>
  - **Is used by:** FastAPI endpoint `/primary`
  - **Located in file:** `primgr.py`
  <br>  

- **get_primary():**
  - **Description**: Gets the node which a given node thinks is the primary
  - **Parameters:** `response` (FastAPI object)
  - **Returns:** JSON, containing the key "Primary" and the value <node name>
  - **Is used by:** `get_reported_primary()`
  - **Located in file:** `repmgr_node.py`

  <br>

- **get_reported_state():**
  - **Description**: Gets the state of the local node from the cache.
  - **Parameters:** `response` (FastAPI object)
  - **Returns:** FastAPI response with JSON body , corresponding to the state of the node
  - **Is used by:** FastAPI endpoint `/state`
  - **Located in file:** `primgr.py`
  <br>  

- **get_state():**
  - **Description**: Gets the state of the local node and caches it.
  - **Parameters:** none
  - **Returns:** int, corresponding to an HTTP response code
  - **Is used by:** `get_reported_state()`
  - **Located in file:** `repmgr_node.py`
<br>

- **get_is_in_recovery_mode():**
  - **Description**: Checks if a given node is in recovery mode
  - **Parameters:** `db_connection`
  - **Returns:** boolean
  - **Is used by:** `get_state()`
  - **Located in file:** `repmgr_node.py`
  <br>

- **get_node_site():**
  - **Description**: Gets the site a given node is in 
  - **Parameters:** `db_connection`,`node_name`
  - **Returns:**  string, containing site ("mr", "mm", etc)
  - **Is used by:** `get_state()`
  - **Located in file:** `repmgr_node.py`
  <br>

- **get_all_other_nodes_in_site():**
  - **Description**: Gets all nodes in a site, other than a given one
  - **Parameters:** `db_connection`,`node_name`
  - **Returns:** list, containing names of nodes
  - **Is used by:** `get_state()`
  - **Located in file:** `repmgr_node.py`
  <br>

- **http_node_reports_primary():**
  - **Description**: Check a given node via http at endpoint `/primary` and see who it reports as primary
  - **Parameters:** `node_to_check`
  - **Returns:** string, containing a node name
  - **Is used by:** `poll_other_nodes()`
  - **Located in file:** `repmgr_node.py`
  <br>

- **poll_other_nodes():**
  - **Description**: Given a list of nodes and a candidate, reports how many of the nodes vote for that candidate
  - **Parameters:** `nodes_to_poll`, `candidate_node`, `num_in_consensus`
  - **Returns:** int, containing the number of nodes voting for the given candidate
  - **Is used by:** `get_state()`
  - **Located in file:** `repmgr_node.py`
  <br>

- **check_consensus():**
  - **Description**: Check that the number of nodes who voted for a candidate is enough to form a consensus
  - **Parameters:** `votes_counted`, `votes_needed`
  - **Returns:** database cursor
  - **Is used by:** `get_state()`
  - **Located in file:** `repmgr_node.py`
  <br>

  - **get_reported_real_primary():**
  - **Description**: Gets the node which most of the cluster thinks is the primary
  - **Parameters:** `response` (FastAPI object)
  - **Returns:** JSON, containing the key "realPrimary" and the value <node name>
  - **Is used by:** FastAPI endpoint `/realPrimary`
  - **Located in file:** `pegasus.py`
  <br>  

- **get_real_primary():**
  - **Description**: Returns the current primary node of the cluster
  - **Parameters:** none
  - **Returns:** string
  - **Is used by:** FastAPI endpoint `/realPrimary`
  - **Located in file:** `repmgr_node.py`
  <br>

- **get_all_nodes():**
  - **Description**: Returns a list of all nodes in the cluster
  - **Parameters:** `db_connection`
  - **Returns:** list, containing names of nodes
  - **Is used by:** `get_real_primary()`
  - **Located in file:** `repmgr_node.py`
  <br>

- **http_node_reports_state():**
  - **Description**:  Check a given node via http at endpoint `/state` and returns the node state
  - **Parameters:** `db_connection`
  - **Returns:** list, containing names of nodes
  - **Is used by:** `gett_real_primary()`
  - **Located in file:** `repmgr_node.py`
  <br>



Caching and connection pool
---------------------------
So as not to spam the local DB with connections (one for each haproxy instance, every few seconds (haproxy health check interval)), 
we only connect to the database through a connection pool at the database driver level. This result is then cached to further reduce databse connection overhead.  
The pool can hold a maximum of 3 connections.   
The cache holds up to 1024 bytes, for up to 20 seconds.

Requirements
------------
**Yum:**
- python >= 3.6 

**pip**
- pip >= 21.0.1
- cachetools
- psycopg2-binary 
- fastapi
- uvicorn
- requests
- SQLAlchemy == 1.3.19

Parameters
-----------
  
- **Variable:** `max_connections_in_pool`
  - **Description**: How many superuser connections to store in the connection pool. 
  - **required**: `no`
<br/>

