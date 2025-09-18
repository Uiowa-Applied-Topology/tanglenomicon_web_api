import pytest
import json
from datetime import datetime, timezone
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from tanglenomicon_data_api.internal import security
from tanglenomicon_data_api.montesinos import generation_endpoint
from tanglenomicon_data_api.montesinos.job import MontesinosJob

from tanglenomicon_data_api.internal import config_store as cfg
from tanglenomicon_data_api.internal import job_queue as jq
from tanglenomicon_data_api.internal import db_connector as dbc
from tanglenomicon_data_api.interfaces.job import JobStateEnum

api: FastAPI = FastAPI()
routers = [security, generation_endpoint]
for ep in routers:
    api.include_router(ep.router)

pytestmark = pytest.mark.anyio


test_path = Path.cwd() / Path("tests/montesinos")


@pytest.fixture
def anyio_backend():
    return "asyncio"


################################################################################
################################################################################
# Test cases for the retrieve_montesinos_job endpoint
################################################################################
################################################################################


@pytest.mark.anyio
async def test_retrieve_montesinos_job_mock_jq(
    get_test_cfg,
    setup_job_queue,
    valid_rational_col,
    valid_montesinos_stencil_col_all_new,
    get_test_jwt,
):
    for i in range(5):
        job_id = f"pending {i}"
        job = MontesinosJob(
            cur_state=JobStateEnum.new,
            timestamp=datetime.now(timezone.utc),
            job_id=job_id,
            crossing_num=0,
            rat_lists=[
                [
                    "h",
                    "e",
                    "l",
                    "l",
                    "o",
                ],
                ["w", "o", "r", "l", "d", "!"],
            ],
        )
        jq._job_queue[job_id] = job
    headers = {"Authorization": f"Bearer {get_test_jwt}"}
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/montesinos/job", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data != None
        assert data["job_id"] == "pending 0"
        assert data["cur_state"] == "pending"
        assert data["client_id"] == "a username"
        assert len(data["rat_lists"]) > 0

        assert jq._job_queue[data["job_id"]]
        assert jq._job_queue[data["job_id"]].cur_state == data["cur_state"]
        assert jq._job_queue[data["job_id"]].client_id == data["client_id"]
        assert jq._job_queue[data["job_id"]].rat_lists == data["rat_lists"]


@pytest.mark.anyio
async def test_retrieve_montesinos_job_jq_empty(
    get_test_cfg,
    setup_job_queue,
    valid_rational_col,
    valid_montesinos_stencil_col_all_new,
    get_test_jwt,
):
    headers = {"Authorization": f"Bearer {get_test_jwt}"}
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/montesinos/job", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data != None
        assert data["cur_state"] == "pending"
        assert data["client_id"] == "a username"
        assert len(data["rat_lists"]) > 0

        assert jq._job_queue[data["job_id"]]
        assert jq._job_queue[data["job_id"]].cur_state == data["cur_state"]
        assert jq._job_queue[data["job_id"]].client_id == data["client_id"]
        assert jq._job_queue[data["job_id"]].rat_lists == data["rat_lists"]


################################################################################
################################################################################
# Test cases for the report_montesinos_job endpoint
################################################################################
################################################################################


@pytest.mark.anyio
async def test_report_montesinos_job_positive(
    get_test_cfg,
    setup_job_queue,
    valid_rational_col,
    valid_montesinos_stencil_col_all_new,
    get_test_jwt,
):
    job_id = "Built job"
    client_id = "a username"
    job = MontesinosJob(
        cur_state=JobStateEnum.pending,
        timestamp=datetime.now(timezone.utc),
        crossing_num=0,
        job_id=job_id,
        client_id=client_id,
        rat_lists=[],
    )
    jq._job_queue[job_id] = job

    headers = {
        "Authorization": f"Bearer {get_test_jwt}",
        "Content-Type": "application/json",
    }
    data = {"job_id": job_id, "mont_list": ["a tangle"]}
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/montesinos/job", json=data, headers=headers)
        assert response.status_code == 200
        res = response.json()
        assert res != None
        assert res["job_id"] == "Built job"
        assert res["accepted"] == True

        assert job
        assert job.cur_state == JobStateEnum.complete
        assert job.client_id == client_id
        assert job._results
        assert job._results.mont_list == data["mont_list"]


@pytest.mark.anyio
async def test_report_montesinos_job_not_in_queue(
    get_test_cfg,
    setup_job_queue,
    valid_rational_col,
    valid_montesinos_stencil_col_all_new,
    get_test_jwt,
):
    job_id = "Built job"
    client_id = "a username"
    job = MontesinosJob(
        cur_state=JobStateEnum.pending,
        timestamp=datetime.now(timezone.utc),
        crossing_num=0,
        job_id=job_id,
        client_id=client_id,
        rat_lists=[],
    )
    jq._job_queue[job_id] = job

    headers = {
        "Authorization": f"Bearer {get_test_jwt}",
        "Content-Type": "application/json",
    }
    data = {"job_id": f"not {job_id}", "mont_list": ["a tangle"]}
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/montesinos/job", json=data, headers=headers)
        assert response.status_code != 200


@pytest.mark.anyio
async def test_report_montesinos_job_not_assigned_to_user(
    get_test_cfg,
    setup_job_queue,
    valid_rational_col,
    valid_montesinos_stencil_col_all_new,
    get_test_jwt,
):
    job_id = "Built job"
    client_id = "a username"
    job = MontesinosJob(
        cur_state=JobStateEnum.pending,
        timestamp=datetime.now(timezone.utc),
        crossing_num=0,
        job_id=job_id,
        client_id=f"not {client_id}",
        rat_lists=[],
    )
    jq._job_queue[job_id] = job

    headers = {
        "Authorization": f"Bearer {get_test_jwt}",
        "Content-Type": "application/json",
    }
    data = {"job_id": job_id, "mont_list": ["a tangle"]}
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/montesinos/job", json=data, headers=headers)
        assert response.status_code != 200
