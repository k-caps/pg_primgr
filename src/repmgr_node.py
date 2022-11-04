#!/usr/bin/python3
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from cachetools import cached, TTLCache
import socket
import requests

HTTP_RETURN_DOWN_CODE: int =  503
HTTP_RETURN_STANDBY_CODE: int = 202
HTTP_RETURN_PRIMARY_CODE: int = 200
HTTP_RETURN_UNVOTED_PRIMARY_CODE: int = 509

CHECK_PORT: int = 5999

PG_DB: str = 'repmgr'
PG_USER: str = 'postgres'
PG_CONNECTION_TIMEOUT: int = 5
PG_STATEMENT_TIMEOUT: int = 5
PG_PORT: int = 5432
PG_APP_NAME: str = 'primgr'

class Repmgr_Node:
    local_con_pool = None

    def __init__(self):
        try:
            self.local_con_pool = create_engine(
                f"postgresql://{PG_USER}@:{PG_PORT}/{PG_DB}?application_name={PG_APP_NAME}",
                pool_pre_ping=True, pool_size=1, max_overflow=3)
        except Exception as ex:
            logging.error(ex)

    #######################################################################################
    #!>                             /primary ENDPOINT FUNCTION                           <!#
    #######################################################################################
    @cached(cache=TTLCache(maxsize=1024, ttl=20))
    def get_primary(self) -> str:
        logging.debug("Starting /primary execution")
        try:
            with self.local_con_pool.connect() as conn:
                try:
                    res = conn.execute(text(
                        "SELECT REPLACE(LOWER(node_name::varchar), '_', '-') as primary FROM repmgr.nodes WHERE type::varchar = 'primary' AND active::varchar = 'true'"))
                    reported_primary = res.fetchone()['primary']
                    return reported_primary

                except Exception as ex:
                    raise (ex)

        except Exception as ex:
            raise ex

        finally:
            logging.debug("Ending /primary execution")


    #######################################################################################
    #!>                             /state ENDPOINT FUNCTION                            <!#
    #######################################################################################
    @cached(cache=TTLCache(maxsize=1024, ttl=20))
    def get_state(self) -> int:
        logging.debug("Starting /state execution")
        logging.debug("I think I might be the primary, checking actual state of node..")
        try:
            with self.local_con_pool.connect() as conn:
                if self.get_is_in_recovery_mode(conn):
                    logging.debug("The local DB is in recovery mode, reporting \"standby\".")
                    return HTTP_RETURN_STANDBY_CODE

                # If we reach this point, that means that I think that I am the primary. I have to see if I'm the only one who thinks that.
                my_name: str = socket.gethostname()
                my_name_for_query: str = my_name.replace('-', '_')
                my_location: str = self.get_node_site(conn, my_name_for_query)
                primary_site_nodes: list = self.get_all_other_nodes_in_site(conn, my_location, my_name_for_query)
                consensus_vote_count: int = 1  # Those who think that I am the primary, including me
                primary_site_node_count: int = len(primary_site_nodes) + 1
                count_needed_for_consensus: int = int(primary_site_node_count / 2) + 1

        except OperationalError:
            logging.warning("/state was unable to connect to local DB, reporting \"down\".")
            return HTTP_RETURN_DOWN_CODE
        except Exception as ex:
            logging.error(ex)
            return HTTP_RETURN_DOWN_CODE

        consensus_vote_count = self.poll_other_nodes(primary_site_nodes, my_name_for_query, consensus_vote_count)
        logging.debug("Ending /state execution")
        http_code_to_return: int = self.check_consensus(consensus_vote_count, count_needed_for_consensus)
        return http_code_to_return


    #######################################################################################
    #!>                             FUNCTIONS USED BY /state                            <!#
    #######################################################################################
    def get_is_in_recovery_mode(self, db_connection) -> bool:
        res = db_connection.execute(text(
            "SELECT pg_is_in_recovery() as is_in_recovery"))  # This query returns a boolean, not a string
        is_standby = res.fetchone()['is_in_recovery']
        return is_standby


    def get_node_site(self, db_connection, node_name: str) -> str:
        res = db_connection.execute(text(
            f"SELECT LOWER(location::varchar) FROM repmgr.nodes WHERE node_name::varchar = '{node_name}'"))
        my_location = res.fetchone()[0]
        return my_location


    def get_all_other_nodes_in_site(self, db_connection, site: str, node_name: str) -> list:
        res = db_connection.execute(text(
            f"SELECT node_name::varchar from repmgr.nodes WHERE location::varchar = '{site}' AND node_name::varchar <> '{node_name}'"))

        site_nodes = res.fetchall()
        return site_nodes


    def poll_other_nodes(self, nodes_to_poll: list, candidate_node: str, num_in_consensus: int) -> int:
        logging.debug("Asking other nodes:")
        logging.debug(
            f"Vars:\n    Nodes to poll: {nodes_to_poll}\n    Candidate_node: {candidate_node}\n    Number in consensus: {num_in_consensus}")
        for node in nodes_to_poll:
            node_name_for_query: str = node[0].replace('_', '-')
            try:
                reported_primary: str = self.http_node_reports_primary(node_name_for_query)
                logging.debug(f"Primary seems to be: {reported_primary}")
                if reported_primary == candidate_node.replace('_', '-'):
                    num_in_consensus += 1
            except requests.ConnectionError as cex:
                logging.warning(cex)
        return num_in_consensus


    def http_node_reports_primary(self, node_to_check: str) -> str:
        reported_primary = requests.get(f"http://{node_to_check}:{CHECK_PORT}/primary", timeout=3)
        if reported_primary.status_code != 200:
            raise requests.ConnectionError("Unable to connect to remote health check port.")
        return reported_primary.json()['Primary']


    '''
    Check that the number of nodes who think I am the primary is the majority of the cluster - at least 2 out of 3 (since we only poll the primary site)
    "(primary_site_node_count/2)+1" evaluates to "more than %50 of nodes (including this one)"
    '''
    def check_consensus(self, votes_counted: int, votes_needed: int) -> int:
        if votes_counted < votes_needed:
            logging.error(
                socket.gethostname() + " was not reported as primary by a majority of the cluster, reporting \"unknown\".")
            return HTTP_RETURN_UNVOTED_PRIMARY_CODE
        else:
            logging.debug(
                socket.gethostname() + " was reported as primary by a majority of the cluster, reporting \"primary\".")
            return HTTP_RETURN_PRIMARY_CODE




