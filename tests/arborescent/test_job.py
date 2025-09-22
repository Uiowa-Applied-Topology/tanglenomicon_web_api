"""Unit tests for the arborescent module."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from mongomock_motor import AsyncMongoMockClient

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


@pytest.fixture
async def setup_job_queue(
    get_test_cfg,
):
    # stub the db connection.
    jq._job_queue = {}
    jq._job_queue["68c3880635edfa4df81b1a46"] = ArborescentJob(
        job_id=str("68c3880635edfa4df81b1a46"),
        cur_state=JobStateEnum.new,
        timestamp=datetime.now(timezone.utc),
        ACN=6,
        grafting_lists=[[]],
    )

    yield  # Provide the data to the test
    jq._job_queue = {}
    # Teardown: Clean up resources (if any) after the test


################################################################################
################################################################################
# Test cases for the get lists flow
################################################################################
################################################################################


################################################################################
#### Positive Tests
################################################################################


def test_get_lists_positive(
    get_test_cfg,
    setup_database,
    setup_job_queue,
):
    dat = _load_data()


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
