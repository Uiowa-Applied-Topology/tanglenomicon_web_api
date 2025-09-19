"""The __main__ file/entry point for tanglenomicon_data_api."""

import asyncio
import logging
from asyncio import AbstractEventLoop
from getpass import getpass, getuser

import typer
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing_extensions import Annotated
from uvicorn import Config as UCfg
from uvicorn import Server as USrv

from .arborescent import generation_endpoint as arbor_ge
from .arborescent import job as arbor_j
from .arborescent import presentation_endpoint as arbor_pe
from .generic import presentation_endpoint as gen_pe
from .internal import config_store, db_connector, job_queue, security
from .montesinos import generation_endpoint as mont_ge
from .montesinos import job as mont_j
from .montesinos import presentation_endpoint as mont_pe
from .rational import presentation_endpoint as rat_pe

logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)


loop: AbstractEventLoop = asyncio.new_event_loop()
api: FastAPI = FastAPI()
routers = [security, mont_ge, mont_pe, arbor_ge, arbor_pe, rat_pe, gen_pe]
job_defs = [
    mont_j.startup_task,
    arbor_j.startup_task,
    arbor_j.time_job,
    arbor_j._set_stencils_complete,
    job_queue.task_clean_complete_jobs,
    job_queue.task_clean_stale_jobs,
]


app = typer.Typer()
origins = ["https://tanglenomicon.com"]

api.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _startup():
    """Executes a collection of tasks at startup of the API."""
    global loop

    db_cfg = config_store.cfg_dict["db-connection-info"]
    db_connector.init_client(
        db_cfg["domain"],
        db_cfg["port"],
        db_cfg["user"],
        db_cfg["password"],
        db_cfg["database"],
    )


def _main():
    """Executes the main task of the API."""
    global api
    global loop
    global routers
    global job_defs

    for endpoint in routers:
        api.include_router(endpoint.router)
    for job_def in job_defs:
        loop.create_task(job_def())

    loop.run_until_complete(USrv(UCfg(app=api, host="0.0.0.0", loop="asyncio")).serve())


@app.command()
def adduser(
    cfg: Annotated[str, typer.Option(prompt="Path to configuration file.")],
    name: Annotated[str, typer.Option(prompt="Username to add")] = None,
):
    """Add a user to the database."""
    config_store.load(cfg)
    _startup()
    if not name:
        name = getuser("Username: ")
    while (pswd := getpass("Password:")) != getpass("Retype Password:"):
        print("Passwords do not match. Please try again.")
    loop.run_until_complete(security.add_user(name, pswd))
    ...


@app.command()
def run(
    cfg: Annotated[str, typer.Option(prompt="Path to configuration file.")],
):
    """Run the server."""
    config_store.load(cfg)

    _startup()

    _main()


if __name__ == "__main__":
    app()