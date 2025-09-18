import pytest
import json
from datetime import datetime, timezone
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from tanglenomicon_data_api.internal import security
from tanglenomicon_data_api.montesinos import presentation_endpoint
from tanglenomicon_data_api.montesinos.job import MontesinosJob

from tanglenomicon_data_api.internal import config_store as cfg
from tanglenomicon_data_api.internal import job_queue as jq
from tanglenomicon_data_api.internal import db_connector as dbc
from tanglenomicon_data_api.interfaces.job import JobStateEnum

api: FastAPI = FastAPI()
routers = [presentation_endpoint]
for ep in routers:
    api.include_router(ep.router)

pytestmark = pytest.mark.anyio


test_path = Path.cwd() / Path("tests/montesinos")


@pytest.fixture
def anyio_backend():
    return "asyncio"


################################################################################
################################################################################
# Test cases for the retrieve_montesinos_tangles endpoint
################################################################################
################################################################################


@pytest.mark.anyio
async def test_retrieve_montesinos_tangles_positive(
    get_test_cfg,
    valid_montesinos_col,
):
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/montesinos/tangles", params={"page_idx": 0, "page_size": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 100


@pytest.mark.anyio
async def test_retrieve_montesinos_tangles_empty_col(
    get_test_cfg,
    empty_montesinos_col,
):
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/montesinos/tangles", params={"page_idx": 0, "page_size": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


@pytest.mark.anyio
async def test_retrieve_montesinos_tangles_empty_list(
    get_test_cfg,
    valid_montesinos_col,
):
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/montesinos/tangles", params={"page_idx": 0, "page_size": 0}
        )
        assert response.status_code == 404


################################################################################
################################################################################
# Test cases for the retrieve_montesinos_job_queue_stats endpoint
################################################################################
################################################################################


@pytest.mark.anyio
async def test_retrieve_montesinos_job_queue_stats_positive(
    get_test_cfg, setup_job_queue, get_test_jwt
):
    headers = {"Authorization": f"Bearer {get_test_jwt}"}
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/montesinos/queue/stats", headers=headers)
        assert response.status_code == 200
        assert response.json() == {
            "queue_length": 0,
            "new": 0,
            "pending": 0,
            "complete": 0,
        }
        for i in range(5):
            job_id = f"pending {i}"
            job = MontesinosJob(
                cur_state=JobStateEnum.pending,
                timestamp=datetime.now(timezone.utc),
                crossing_num=0,
                job_id=job_id,
                rat_lists=[],
            )
            jq._job_queue[job_id] = job
        for i in range(3):
            job_id = f"new {i}"
            job = MontesinosJob(
                cur_state=JobStateEnum.new,
                timestamp=datetime.now(timezone.utc),
                crossing_num=0,
                job_id=job_id,
                rat_lists=[],
            )
            jq._job_queue[job_id] = job
        for i in range(6):
            job_id = f"complete {i}"
            job = MontesinosJob(
                cur_state=JobStateEnum.complete,
                timestamp=datetime.now(timezone.utc),
                crossing_num=0,
                job_id=job_id,
                rat_lists=[],
            )
            jq._job_queue[job_id] = job

        response = await ac.get("/montesinos/queue/stats", headers=headers)
        assert response.status_code == 200
        assert response.json() == {
            "queue_length": 14,
            "new": 3,
            "pending": 5,
            "complete": 6,
        }
