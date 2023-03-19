#!/usr/bin/python3
import logging
from logging.handlers import RotatingFileHandler
from sqlalchemy.exc import OperationalError
from fastapi import FastAPI, Response, status
from repmgr_node import Repmgr_Node

app = FastAPI()


LOGFILE_NAME: str = "/var/log/primgr/primgr.log"
logging.basicConfig(handlers=[RotatingFileHandler(LOGFILE_NAME, maxBytes=80000000, backupCount=2)],
                    format='%(asctime)s - [%(levelname)s] - %(message)s',
                    datefmt='%d-%m-%Y %H:%M:%S', level=logging.INFO)


HTTP_RETURN_DOWN_CODE: int =  503
HTTP_RETURN_STANDBY_CODE: int = 202
HTTP_RETURN_PRIMARY_CODE: int = 200
HTTP_RETURN_UNVOTED_PRIMARY_CODE: int = 509

CHECK_PORT: int = 5999


@app.on_event("startup")
def create_node_instance():
    global repmgr_node
    repmgr_node = Repmgr_Node()


@app.get("/realPrimary")
def get_reported_real_primary(response: response):
    try:
        real_primary = repmgr_node.get_real_primary()
        return {"realPrimary": real_primary}

    except OperationalError:
        logging.warning("/primary was unable to connect to local DB, reporting \"down\".")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"State": "Down"}

    except Exception as ex:
        logging.error(ex)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"State": "Unknown"}        
    

@app.get("/primary")
def get_reported_primary(response: Response):
    try:
        primary = repmgr_node.get_primary()
        return {"Primary": primary}

    except OperationalError:
        logging.warning("/primary was unable to connect to local DB, reporting \"down\".")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"State": "Down"}

    except Exception as ex:
        logging.error(ex)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"State": "Down"}


@app.get("/state")
def get_reported_state(response: Response) -> dict:
    logging.info("Requesting state from cache")
    response.status_code = repmgr_node.get_state()
    if response.status_code == HTTP_RETURN_DOWN_CODE:
            return {"State": "Down"}
    elif response.status_code == HTTP_RETURN_STANDBY_CODE:
        return {"State": "Standby"}
    elif response.status_code == HTTP_RETURN_PRIMARY_CODE:
        return {"State": "Primary"}
    else:
        return {"State": "Unknown"}
