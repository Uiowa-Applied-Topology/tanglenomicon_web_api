"""An implementation of the job interface for Arborescent jobs."""

import asyncio
import copy
import hashlib
import itertools
import logging
import math
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import List

from bson import ObjectId
from dacite import from_dict
from pymongo import InsertOne, UpdateOne

from ..interfaces.job import GenerationJob, GenerationJobResults, JobStateEnum
from ..internal import config_store, job_queue
from . import orm

logger = logging.getLogger("uvicorn")

_jobbuild_sem: asyncio.Semaphore = asyncio.Semaphore(3)
_store_sem: asyncio.Semaphore = asyncio.Semaphore(10)
_stencil_cfg: orm.StencilCfg = None
_debounce: datetime = None


def _open_stencil(acn: int):
    return {
        "$and": [
            {"state": {"$ne": orm.StencilStateEnum.complete}},
            {"state": {"$ne": orm.StencilStateEnum.no_headroom}},
            {"ACN": {"$lte": acn}},
            {"rootstock_acn": {"$ne": 0}},
            {"_id": {"$ne": "config"}},
        ]
    }


def _complete_stencil(acn: int):
    return {
        "$and": [
            {"state": orm.StencilStateEnum.complete},
            {"ACN": {"$lte": acn}},
            {"rootstock_acn": {"$ne": 0}},
            {"_id": {"$ne": "config"}},
        ]
    }


def _not_complete_filter(acn: int):
    return {
        "$and": [
            {"ACN": {"$lte": acn}},
            {"state": {"$ne": orm.StencilStateEnum.complete}},
            {"_id": {"$ne": "config"}},
        ]
    }


async def _get_stencil_config() -> orm.StencilCfg:
    stencil_col = orm.get_stencil_collection()
    stencil = await stencil_col.find_one({"_id": "config"})
    return from_dict(data_class=orm.StencilCfg, data=stencil)


class ArborescentJobResults(GenerationJobResults):
    """The implementation of job results for Arborescent jobs."""

    arbor_list: List[orm.AnborescentTangleResult]


class ArborescentJob(GenerationJob):
    """The implementation of job for Arborescent tangles."""

    grafting_lists: List[List[List[str]]]
    ACN: int
    _jobdb: orm.JobDB
    _page: List[ObjectId] = None
    _results: ArborescentJobResults = None

    def set_jobdb(self, job: orm.JobDB):
        self._jobdb = job

    def get_jobdb(self) -> orm.JobDB:
        return self._jobdb

    async def _get_lists(self, pipeline):
        lis_p = []
        lis_n = []
        lis_u = []
        col = orm.get_arborescent_collection()
        tan_lis = [
            tang
            async for tang in col.find(
                pipeline, projection={"notation": 1, "positivity": 1}
            ).limit(
                int(config_store.cfg_dict["tangle-classes"]["arborescent"]["page_size"])
            )
        ]

        lis_p.extend(
            [tang["notation"] for tang in tan_lis if tang["positivity"] == "positive"]
        )
        lis_n.extend(
            [tang["notation"] for tang in tan_lis if tang["positivity"] == "negative"]
        )
        lis_u.extend(
            [tang["notation"] for tang in tan_lis if tang["positivity"] == "neutral"]
        )
        return lis_p, lis_n, lis_u

    async def _get_rootstocklist(self, acn: int, page: ObjectId):
        pipeline = {"ACN": acn, "_id": {"$gte": page}}
        return await self._get_lists(pipeline)

    async def _get_scionlist(self, acn: int, page: ObjectId):
        pipeline = {"ACN": acn, "is_good": True, "_id": {"$gte": page}}
        return await self._get_lists(pipeline)

    async def get_lists(self):
        rp, rn, ru = await self._get_rootstocklist(
            self._jobdb.rootstock_acn, self._jobdb.cursor[0]
        )
        sp, sn, su = await self._get_scionlist(
            self._jobdb.scion_acn, self._jobdb.cursor[1]
        )
        self.grafting_lists = [
            [rp, ["positive"] * len(rp), sp, ["positive"] * len(sp)],
            [rp, ["positive"] * len(rp), su, ["neutral"] * len(su)],
            [ru, ["neutral"] * len(ru), sp, ["positive"] * len(sp)],
            [rn, ["negative"] * len(rn), sn, ["negative"] * len(sn)],
            [rn, ["negative"] * len(rn), su, ["neutral"] * len(su)],
            [ru, ["neutral"] * len(ru), sn, ["negative"] * len(sn)],
            [ru, ["neutral"] * len(ru), su, ["neutral"] * len(su)],
        ]

    async def _aiter_tangles(self):
        for aiter_tang in self._results.arbor_list:
            yield aiter_tang

    async def store(self) -> bool:
        """Store the current job into the Arborescent tangle collection.

        Returns
        -------
        bool
            Indicator for success of storage.
        """
        job_col = orm.get_job_collection()
        arborescent_col = orm.get_arborescent_collection()
        try:
            tangles_2_store = []
            if len(self._results.arbor_list) > 0:
                async for tang in self._aiter_tangles():
                    tangles_2_store.append(
                        UpdateOne(
                            {"notation": str(tang.notation)},
                            {
                                "$set": {
                                    "positivity": tang.positivity,
                                    "is_good": tang.is_good,
                                    "ACN": tang.ACN,
                                }
                            },
                            upsert=True,
                        )
                    )
                    if len(tangles_2_store) > 1000:
                        if (
                            await arborescent_col.bulk_write(
                                tangles_2_store, ordered=False
                            )
                        ).bulk_api_result["writeErrors"]:
                            raise ValueError("Write errors")
                        tangles_2_store = []
                if len(tangles_2_store) > 0:
                    if (
                        await arborescent_col.bulk_write(tangles_2_store, ordered=False)
                    ).bulk_api_result["writeErrors"]:
                        raise ValueError("Write errors")
            await job_col.delete_one({"_id": self._jobdb._id})
            if await job_col.find_one({"_id": self._jobdb._id}):
                raise ValueError("Delete errors")
                ...

        except Exception as e:
            logger.error(f"Exception while storing arborescent tangles: {e}")
            return False
        return True

    def update_results(self, res: ArborescentJobResults):
        """Update the job with the reported results."""
        self._results = res


async def load_jobs():
    global _stencil_cfg
    job_col = orm.get_job_collection()
    num_jobs = (
        config_store.cfg_dict["job-queue"]["min-new-count"]
        - (await job_queue.get_job_statistics(ArborescentJob))["queue_length"]
    )
    if num_jobs > 0:
        async for jobdb in job_col.find({"state": orm.JobDBStateEnum.new}).limit(
            num_jobs
        ):
            job = from_dict(data_class=orm.JobDB, data=jobdb)
            jobint = ArborescentJob(
                job_id=str(job._id),
                cur_state=JobStateEnum.new,
                timestamp=datetime.now(timezone.utc),
                ACN=job.rootstock_acn + job.scion_acn,
                grafting_lists=[[]],
            )
            jobint.set_jobdb(copy.deepcopy(job))
            await job_queue.enqueue_job(jobint)
            await job_col.update_one(
                {"_id": job._id}, {"$set": {"state": orm.JobDBStateEnum.started}}
            )


async def _build_cursor_list(mongo_filter):
    arbor_col = orm.get_arborescent_collection()
    page_list = []
    cursor = (await arbor_col.find_one(mongo_filter, {"_id": 1}))["_id"]
    page_list.append(cursor)
    while tangdb := (
        await arbor_col.find(
            {"$and": [mongo_filter, {"_id": {"$gte": cursor}}]}, {"_id": 1}
        )
        .skip(int(config_store.cfg_dict["tangle-classes"]["arborescent"]["page_size"]))
        .to_list(1)
    ):
        cursor = tangdb[0]["_id"]
        page_list.append(tangdb[0]["_id"])
    return page_list


async def _process_stencil(stencil: orm.StencilDB):
    global _jobbuild_sem
    stencil_col = orm.get_stencil_collection()
    job_col = orm.get_job_collection()
    async with _jobbuild_sem:
        await stencil_col.update_one(
            {"_id": stencil._id}, {"$set": {"state": orm.StencilStateEnum.started}}
        )

        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(_build_cursor_list({"ACN": stencil.rootstock_acn})),
                tg.create_task(
                    _build_cursor_list({"ACN": stencil.scion_acn, "is_good": True})
                ),
            ]

        async def _prod(l1):
            for i in l1:
                yield i

        async for root_idx in _prod(tasks[0].result()):
            async for scion_idx in _prod(tasks[1].result()):
                await job_col.insert_one(
                    {
                        "state": orm.JobDBStateEnum.new,
                        "rootstock_acn": stencil.rootstock_acn,
                        "scion_acn": stencil.scion_acn,
                        "cursor": copy.deepcopy([root_idx, scion_idx]),
                    }
                )

        await stencil_col.update_one(
            {"_id": stencil._id}, {"$set": {"state": orm.StencilStateEnum.complete}}
        )
        ...


async def _build_jobs(stencil_cfg: orm.StencilCfg):
    stencil_col = orm.get_stencil_collection()
    async with asyncio.TaskGroup() as tg:
        async for stencildb in stencil_col.find(
            _open_stencil(stencil_cfg.current_completed_acn + 1)
        ):
            stencil = from_dict(data_class=orm.StencilDB, data=stencildb)
            tg.create_task(_process_stencil(stencil))


async def startup_task():
    """Task to run at startup to initialize Arborescent jobs."""
    global _stencil_cfg
    job_col = orm.get_job_collection()
    _stencil_cfg = await _get_stencil_config()
    async for jobdb in job_col.find({"state": orm.JobDBStateEnum.started}):
        job = from_dict(data_class=orm.JobDB, data=jobdb)
        jobint = ArborescentJob(
            job_id=str(job._id),
            cur_state=JobStateEnum.new,
            timestamp=datetime.now(timezone.utc),
            ACN=job.rootstock_acn + job.scion_acn,
            grafting_lists=[[]],
        )
        jobint.set_jobdb(job)

        await job_queue.enqueue_job(jobint)
    await _build_jobs(_stencil_cfg)
    ...


# async def _set_stencils_complete():
#     global _stencil_cfg
#     while True:
#         await asyncio.sleep(5)
#         ...


async def time_job():
    """Task to run at startup to initialize Arborescent jobs."""
    global _stencil_cfg
    await asyncio.sleep(2)
    stencil_col = orm.get_stencil_collection()
    job_col = orm.get_job_collection()
    while _stencil_cfg.current_completed_acn < _stencil_cfg.max_acn:
        await load_jobs()
        jqstats = await job_queue.get_job_statistics(ArborescentJob)
        open_stencils = await stencil_col.count_documents(
            _open_stencil(_stencil_cfg.current_completed_acn + 1)
        )
        job_count = await job_col.count_documents({})
        if (jqstats["queue_length"] == 0) and (open_stencils == 0) and (job_count == 0):
            _stencil_cfg.current_completed_acn += 1
            await stencil_col.update_one(
                {"_id": "config"},
                {"$set": {"current_completed_acn": _stencil_cfg.current_completed_acn}},
            )
            await _build_jobs(_stencil_cfg)
        await asyncio.sleep(2)
