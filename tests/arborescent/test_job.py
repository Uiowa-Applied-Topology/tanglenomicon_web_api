"""Unit tests for the montesinos module."""

import pytest
import json
from datetime import datetime, timezone
from mongomock_motor import AsyncMongoMockClient
from pathlib import Path
from tanglenomicon_data_api.montesinos.job import (
    get_jobs,
    startup_task,
    MontesinosJob,
    MontesinosJobResults,
)
from tanglenomicon_data_api.internal import config_store as cfg
from tanglenomicon_data_api.internal import job_queue as jq
from tanglenomicon_data_api.internal import db_connector as dbc
from tanglenomicon_data_api.interfaces.job import JobStateEnum


pytestmark = pytest.mark.anyio

test_path = Path.cwd() / Path("tests/montesinos")


def _load_data(path: Path) -> dict:
    dat = None
    with open(path) as f:
        dat = json.load(f)
    return dat
    ...


@pytest.fixture
def anyio_backend():
    return "asyncio"


################################################################################
################################################################################
# Test cases for the get_jobs function
################################################################################
################################################################################


async def test_get_jobs_positive(
    get_test_cfg,
    setup_database,
    setup_job_queue,
    valid_rational_col,
    valid_montesinos_stencil_col,
):
    await get_jobs(3)
    jobs = _load_data(test_path / "valid_jobs_for_get_jobs.json")
    enqueued_jobs = [
        jq._job_queue[i].rat_lists
        for i in jq._job_queue
        if isinstance(jq._job_queue[i], MontesinosJob)
    ]
    for job in jobs:
        assert job in enqueued_jobs

    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["stencil_col_name"]]

    stencils = {}
    async for s in col.find({}):
        stencils[s["str_rep"]] = s
    assert len(stencils["10 10"]["open_jobs"]) == 0
    assert len(stencils["2 10 10"]["open_jobs"]) == 1
    assert len(stencils["3 10 10"]["open_jobs"]) == 1
    assert len(stencils["11 10"]["open_jobs"]) == 2
    assert stencils["10 10"]["state"] == 3
    assert stencils["2 10 10"]["state"] == 2
    assert stencils["3 10 10"]["state"] == 2
    assert stencils["11 10"]["state"] == 2
    ...


async def test_get_jobs_stencil_collection_is_empty(
    get_test_cfg,
    setup_database,
    setup_job_queue,
    valid_rational_col,
    empty_montesinos_stencil_col,
):
    await get_jobs(2)
    enqueued_jobs = [
        jq._job_queue[i].rat_lists
        for i in jq._job_queue
        if isinstance(jq._job_queue[i], MontesinosJob)
    ]
    assert [] == enqueued_jobs
    ...


async def test_get_jobs_rational_collection_is_empty(
    get_test_cfg,
    setup_database,
    setup_job_queue,
    empty_rational_col,
    valid_montesinos_stencil_col,
):
    try:
        await get_jobs(2)
        assert False
    except:
        assert True
    ...


async def test_get_jobs_request_zero(
    get_test_cfg,
    setup_database,
    setup_job_queue,
    valid_rational_col,
    valid_montesinos_stencil_col,
):
    await get_jobs(0)
    enqueued_jobs = [
        jq._job_queue[i].rat_lists
        for i in jq._job_queue
        if isinstance(jq._job_queue[i], MontesinosJob)
    ]
    assert [] == enqueued_jobs
    ...


################################################################################
################################################################################
# Test cases for the startup_task function
################################################################################
################################################################################


async def test_startup_task_positive(
    get_test_cfg, setup_job_queue, valid_rational_col, valid_montesinos_stencil_col
):
    await startup_task()
    jobs = _load_data(test_path / "valid_jobs_for_startup.json")
    enqueued_jobs = [
        jq._job_queue[i].rat_lists
        for i in jq._job_queue
        if isinstance(jq._job_queue[i], MontesinosJob)
    ]
    for job in jobs:
        assert job in enqueued_jobs

    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["stencil_col_name"]]

    stencils = {}
    async for s in col.find({}):
        stencils[s["str_rep"]] = s
    assert len(stencils["10 10"]["open_jobs"]) == 0
    assert len(stencils["2 10 10"]["open_jobs"]) == 1
    assert len(stencils["3 10 10"]["open_jobs"]) == 0
    assert len(stencils["11 10"]["open_jobs"]) == 1
    assert stencils["10 10"]["state"] == 3
    assert stencils["2 10 10"]["state"] == 2
    assert stencils["3 10 10"]["state"] == 1
    assert stencils["11 10"]["state"] == 1
    ...


async def test_startup_task_positive_all_new(
    get_test_cfg,
    setup_job_queue,
    valid_rational_col,
    valid_montesinos_stencil_col_all_new,
):
    await startup_task()
    jobs = _load_data(test_path / "valid_jobs_for_startup_all_new.json")
    enqueued_jobs = [
        jq._job_queue[i].rat_lists
        for i in jq._job_queue
        if isinstance(jq._job_queue[i], MontesinosJob)
    ]
    for job in jobs:
        assert job in enqueued_jobs

    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["stencil_col_name"]]

    stencils = {}
    async for s in col.find({}):
        stencils[s["str_rep"]] = s
    assert len(stencils["10 10"]["open_jobs"]) == 1
    assert len(stencils["2 10 10"]["open_jobs"]) == 1
    assert len(stencils["3 10 10"]["open_jobs"]) == 0
    assert len(stencils["11 10"]["open_jobs"]) == 0
    assert stencils["10 10"]["state"] == 2
    assert stencils["2 10 10"]["state"] == 2
    assert stencils["3 10 10"]["state"] == 1
    assert stencils["11 10"]["state"] == 0
    ...


################################################################################
################################################################################
# Test cases for the MontesinosJob.store function
################################################################################
################################################################################


async def test_mj_store_task_positive(
    get_test_cfg,
    setup_database,
    setup_job_queue,
    valid_montesinos_stencil_col,
    empty_montesinos_col,
):
    job_id = "A test job"
    results_tangs = ["a", "b", "c"]
    res = MontesinosJobResults(job_id=job_id, mont_list=results_tangs)
    job = MontesinosJob(
        cur_state=JobStateEnum.pending,
        timestamp=datetime.now(timezone.utc),
        crossing_num=0,
        job_id=job_id,
        rat_lists=[],
    )
    job.update_results(res)
    jq._job_queue[job_id] = job

    await job.store()

    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["stencil_col_name"]]

    stencil = await col.find_one({"open_jobs.job_id": job_id})
    assert stencil == None

    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["col_name"]]
    async for m in col.find({}):
        assert m["_id"] in results_tangs

    ...
