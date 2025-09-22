"""Unit tests for the arborescent module."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from dacite import from_dict

from tanglenomicon_data_api.arborescent import orm
from tanglenomicon_data_api.arborescent.job import (
    ArborescentJob,
    ArborescentJobResults,
    load_jobs,
    startup_task,
    time_job,
)
from tanglenomicon_data_api.interfaces.job import JobStateEnum
from tanglenomicon_data_api.internal import config_store as cfg
from tanglenomicon_data_api.internal import db_connector as dbc
from tanglenomicon_data_api.internal import job_queue as jq

pytestmark = pytest.mark.anyio

test_path = Path.cwd() / Path("tests/arborescent")


def _load_data(path: Path) -> dict:
    dat = None
    with open(path) as f:
        dat = json.load(f)
    return dat


@pytest.fixture
def anyio_backend():
    return "asyncio"


################################################################################
################################################################################
# Test cases for the get lists flow
################################################################################
################################################################################


################################################################################
#### Positive Tests
################################################################################


async def test_get_lists_positive(
    get_test_cfg,
    setup_database,
    valid_arborescent_col,
    setup_job_queue,
):
    job_db = {
        "_id": ObjectId("68c3880635edfa4df81b1a46"),
        "state": 0,
        "rootstock_acn": 2,
        "scion_acn": 4,
        "cursor": ["68c3886f35edfa4df81b1ba8", "68c3886f35edfa4df81b1b74"],
    }
    # stub the db connection.
    job = ArborescentJob(
        job_id=str("68c3880635edfa4df81b1a46"),
        cur_state=JobStateEnum.new,
        timestamp=datetime.now(timezone.utc),
        ACN=6,
        grafting_lists=[[]],
    )
    job.set_jobdb(from_dict(data_class=orm.JobDB, data=job_db))
    await job.get_lists()


################################################################################
#### Negative Tests
################################################################################


def test_get_lists_negative(): ...


################################################################################
################################################################################
# Test cases for the Load jobs flow
################################################################################
################################################################################


################################################################################
#### Positive Tests
################################################################################


def test_load_jobs_positive(): ...


################################################################################
#### Negative Tests
################################################################################


def test_load_jobs_empty_stens(): ...
def test_load_jobs_empty_arbor(): ...
def test_load_jobs_req_zero(): ...


################################################################################
################################################################################
# Test cases for the Startup flow
################################################################################
################################################################################


################################################################################
#### Positive Tests
################################################################################


def test_startup_positive(): ...


################################################################################
#### Negative Tests
################################################################################

# None


################################################################################
################################################################################
# Test cases for the Time task flow
################################################################################
################################################################################


################################################################################
#### Positive Tests
################################################################################


def test_time_task_sten_processed(): ...
def test_time_task_queue_filled(): ...
def test_time_task_inc_TCN(): ...


################################################################################
#### Negative Tests
################################################################################


def test_time_task_empty_sten(): ...


def test_time_task_empty_arbor(): ...


################################################################################
################################################################################
# Test cases for the Store flow
################################################################################
################################################################################


################################################################################
#### Positive Tests
################################################################################


def test_store_positive(): ...


################################################################################
#### Negative Tests
################################################################################

# None
