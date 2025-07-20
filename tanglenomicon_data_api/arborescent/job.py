"""An implementation of the job interface for Arborescent jobs."""
import asyncio
from datetime import datetime, timezone, timedelta
from ..interfaces.job import GenerationJob, GenerationJobResults, JobStateEnum
from ..internal import config_store, job_queue
from . import orm
from typing import List
from dacite import from_dict
from dataclasses import asdict
import math
import copy
from bson import ObjectId
from pymongo import UpdateOne
import logging
import hashlib
import itertools

logger = logging.getLogger("uvicorn")

_jobbuild_sem: asyncio.Semaphore = asyncio.Semaphore(10)
_store_sem: asyncio.Semaphore = asyncio.Semaphore(10)
_stencil_cfg: orm.StencilCfg = None
_debounce: datetime = None


def _open_zero_stencil(acn: int):
    return {"$and": [
        {"state": {"$ne": orm.StencilStateEnum.complete}},
        {"state": {"$ne": orm.StencilStateEnum.no_headroom}},
        {"ACN": {"$lte": acn}},
        {"rootstock_acn": 0},
        {"_id": {"$ne": "config"}},
    ]
    }


def _open_nonzero_stencil(acn: int):
    return {
        "$and": [
            {"state": {"$ne": orm.StencilStateEnum.complete}},
            {"state": {"$ne": orm.StencilStateEnum.no_headroom}},
            {"ACN": {"$lte": acn}},
            {"rootstock_acn": {"$ne": 0}},
            {"_id": {"$ne": "config"}},
        ]
    }


def _nonzero_stencil(acn: int):
    return {
        "$and": [
            {"ACN": {"$lte": acn}},
            {"rootstock_acn": {"$ne": 0}},
            {"_id": {"$ne": "config"}},
        ]
    }


def _complete_zero_stencil(acn: int):
    return {
        "$and": [
            {"state": orm.StencilStateEnum.complete},
            {"ACN": acn},
            {"rootstock_acn": 0},
            {"_id": {"$ne": "config"}},
        ]
    }


def _complete_nonzero_stencil(acn: int):
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


async def _update_stencil_config():
    global _stencil_cfg
    stencil_col = orm.get_stencil_collection()
    arbor_col = orm.get_arborescent_collection()
    acn = _stencil_cfg.current_completed_acn
    while (
        0
        == await stencil_col.count_documents(
        _not_complete_filter(acn + 1),
    )
        and acn < _stencil_cfg.max_acn
    ):
        acn += 1
    if _stencil_cfg.current_completed_acn < acn:
        _stencil_cfg.current_counts[
            _stencil_cfg.current_completed_acn] = await arbor_col.count_documents(
            {"ACN": _stencil_cfg.current_completed_acn}
        )
        _stencil_cfg.current_good_counts[
            _stencil_cfg.current_completed_acn
        ] = await arbor_col.count_documents(
            {"$and": [{"ACN": _stencil_cfg.current_completed_acn}, {"is_good": True}]}
        )
        _stencil_cfg.current_completed_acn = acn
        await stencil_col.replace_one({"_id": _stencil_cfg._id}, asdict(_stencil_cfg))


async def _update_stencil_zero_config():
    global _stencil_cfg
    stencil_col = orm.get_stencil_collection()
    arbor_col = orm.get_arborescent_collection()
    _stencil_cfg.current_good_counts[
        _stencil_cfg.current_completed_acn + 1
        ] = await arbor_col.count_documents(
        {"$and": [{"ACN": _stencil_cfg.current_completed_acn + 1}, {"is_good": True}]}
    )
    await stencil_col.replace_one({"_id": _stencil_cfg._id}, asdict(_stencil_cfg))


class ArborescentJobResults(GenerationJobResults):
    """The implementation of job results for Arborescent jobs."""

    arbor_list: List[orm.ArborescentTangle]


class ArborescentJob(GenerationJob):
    """The implementation of job for Arborescent tangles."""

    grafting_lists: List[List[List[str]]]
    ACN: int
    rootstock_acn: int
    scion_acn: int
    _page: List[ObjectId] = None
    _results: ArborescentJobResults = None

    def set_page(self, page: List[ObjectId]):
        self._page = page

    def get_page(self):
        return self._page

    async def _get_lists(self, pipeline):
        lis_p = []
        lis_n = []
        lis_u = []
        col = orm.get_arborescent_collection()
        tan_lis = [tang async for tang in
                   col.find(pipeline, projection={"notation": 1, "positivity": 1}).limit(
                       int(config_store.cfg_dict["tangle-classes"]["arborescent"][
                               "page_size"]))]

        lis_p.extend([tang["notation"] for tang in tan_lis if tang["positivity"] == "positive"])
        lis_n.extend([tang["notation"] for tang in tan_lis if tang["positivity"] == "negative"])
        lis_u.extend([tang["notation"] for tang in tan_lis if tang["positivity"] == "neutral"])
        return lis_p, lis_n, lis_u

    async def _get_rootstocklist(self, acn: int, page: ObjectId):
        pipeline = {"_id": {"$gte": page}, "ACN": acn}
        return await self._get_lists(pipeline)

    async def _get_scionlist(self, acn: int, page: ObjectId):
        pipeline = {"_id": {"$gte": page}, "ACN": acn, "is_good": True}
        return await self._get_lists(pipeline)

    async def get_lists(self):

        rp, rn, ru = await self._get_rootstocklist(self.rootstock_acn, self._page[0])
        sp, sn, su = await self._get_scionlist(self.scion_acn, self._page[1])
        self.grafting_lists = [
            [rp, ["positive"] * len(rp), sp, ["positive"] * len(sp)],
            [rp, ["positive"] * len(rp), su, ["neutral"] * len(su)],
            [ru, ["neutral"] * len(ru), sp, ["positive"] * len(sp)],
            [rn, ["negative"] * len(rn), sn, ["negative"] * len(sn)],
            [rn, ["negative"] * len(rn), su, ["neutral"] * len(su)],
            [ru, ["neutral"] * len(ru), sn, ["negative"] * len(sn)],
            [ru, ["neutral"] * len(ru), su, ["neutral"] * len(su)],
        ]

    async def _update_stencil(self):
        """Update the parent stencil."""
        stencil_col = orm.get_stencil_collection()
        try:
            stencildb = await stencil_col.find_one({"open_jobs.job_id": self.job_id})
            stencil = from_dict(
                data_class=orm.StencilDB,
                data=(stencildb),
            )
        except Exception as e:
            logger.error(f"Exception while storing arborescent tangles: {e}")
            ret_val = False
            pass

        result = await stencil_col.update_one({"_id": stencil._id},
                                              {"$pull": {"open_jobs": {"job_id": self.job_id}}})
        ...

    async def store(self) -> bool:
        """Store the current job into the Arborescent tangle collection.

        Returns
        -------
        bool
            Indicator for success of storage.
        """
        global _store_sem
        ret_val = False
        async with _store_sem:
            arborescent_col = orm.get_arborescent_collection()

            async def aiter_results():
                for tang in self._results.arbor_list:
                    yield tang

            tangles_2_store = [
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
                async for tang in aiter_results()
            ]
            # tangles_2_store.extend([
            #     UpdateOne(
            #         {"notation": str(tang.notation)},
            #         {"$push": {"parents": [rs_set[0], rs_set[1]]}},
            #         upsert=True,
            #     )
            #     async for tang in aiter_results() for rs_set in tang.parents
            # ])

            ret_val = True
            if len(tangles_2_store) > 0:
                try:
                    await arborescent_col.bulk_write(tangles_2_store, ordered=False)
                except Exception as e:
                    logger.error(f"Exception while storing arborescent tangles: {e}")
                    ret_val = False
                    pass
            await self._update_stencil()
        return ret_val

    def update_results(self, res: ArborescentJobResults):
        """Update the job with the reported results."""
        self._results = res


async def _build_cursor_list(mongo_filter):
    arbor_col = orm.get_arborescent_collection()
    page_list = []
    cursor = \
        (await arbor_col.find_one(mongo_filter, {"_id": 1}))[
            "_id"]
    page_list.append(cursor)
    while tangdb := (await arbor_col.find(
        {"$and": [mongo_filter, {"_id": {"$gte": cursor}}]},
        {"_id": 1}).skip(
        int(config_store.cfg_dict["tangle-classes"]["arborescent"]["page_size"])).to_list(
        1)):
        cursor = tangdb[0]["_id"]
        page_list.append(tangdb[0]["_id"])
    return page_list


async def _build_jobs(stencil: orm.StencilDB):
    global _jobbuild_sem
    stencil_col = orm.get_stencil_collection()
    jobs = []
    async with _jobbuild_sem:
        await stencil_col.update_one({"_id": stencil._id},
                                     {"$set": {"state": orm.StencilStateEnum.started}})

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_build_cursor_list({"ACN": stencil.rootstock_acn})),
                     tg.create_task(_build_cursor_list(
                         {"ACN": stencil.scion_acn, "is_good": True}))]

        async def prod(l1, l2):
            for i, j in itertools.product(l1, l2):
                yield i, j

        async for root_idx, scion_idx in prod(tasks[0].result(),
                                              tasks[1].result(), ):
            m = hashlib.sha256()
            m.update(str(stencil._id).encode("utf-8"))
            m.update(str(root_idx).encode("utf-8"))
            m.update(str(scion_idx).encode("utf-8"))
            m.digest()
            job_id = m.hexdigest()
            # stencil.job_backlog.append(
            #     orm.StencilJobDB(job_id=job_id, cursor=copy.deepcopy([root_idx, scion_idx]))
            # )
            jobs.append(UpdateOne({"_id": stencil._id}, {"$push": {"job_backlog": {
                "job_id": job_id,
                "cursor": copy.deepcopy([root_idx, scion_idx])}}}))
        result = await stencil_col.bulk_write(jobs, ordered=False)
        await stencil_col.update_one({"_id": stencil._id},
                              {"$set": {"state": orm.StencilStateEnum.no_headroom}})
        # await stencil_col.replace_one({"_id": stencil._id}, asdict(stencil))
        ...


async def _build_nonzero_jobs(stencil_cfg: orm.StencilCfg):
    stencil_col = orm.get_stencil_collection()
    async with asyncio.TaskGroup() as tg:
        async for stencildb in stencil_col.find(
            _open_nonzero_stencil(stencil_cfg.current_completed_acn + 1)):
            stencil = from_dict(data_class=orm.StencilDB, data=stencildb)
            await stencil_col.update_one({"_id": stencil._id},
                                         {"$set": {"state": orm.StencilStateEnum.started}})
            tg.create_task(_build_jobs(stencil))


...


async def _build_zero_jobs(stencil_cfg: orm.StencilCfg):
    stencil_col = orm.get_stencil_collection()
    async with asyncio.TaskGroup() as tg:
        stencils = await stencil_col.find(
            _open_zero_stencil(stencil_cfg.current_completed_acn + 1)).to_list(None)
        for stencildb in stencils:
            tg.create_task(_build_jobs(from_dict(data_class=orm.StencilDB, data=stencildb)))
    ...


async def load_jobs():
    global _stencil_cfg
    loaded = False
    stencil_col = orm.get_stencil_collection()
    async for stencildb in stencil_col.find(
        {"job_backlog": {"$exists": True, "$not": {"$size": 0}}}):
        stencil = from_dict(data_class=orm.StencilDB, data=stencildb)
        while (await job_queue.get_job_statistics(ArborescentJob))["queue_length"] < \
            config_store.cfg_dict["job-queue"]["min-new-count"] and len(
            stencil.job_backlog) > 0:
            loaded = True
            job = ArborescentJob(
                cur_state=JobStateEnum.new,
                timestamp=datetime.now(timezone.utc),
                job_id=copy.deepcopy(stencil.job_backlog[0].job_id),
                grafting_lists=[[]],
                ACN=stencil.ACN,
                rootstock_acn=stencil.rootstock_acn,
                scion_acn=stencil.scion_acn)
            job.set_page(stencil.job_backlog[0].cursor)
            result = await stencil_col.bulk_write(
                [UpdateOne({"_id": stencil._id}, {"$push": {"open_jobs": {
                    "job_id": stencil.job_backlog[0].job_id,
                    "cursor": stencil.job_backlog[0].cursor}}}),
                 UpdateOne({"_id": stencil._id}, {"$pull": {"job_backlog": {
                     "job_id": stencil.job_backlog[0].job_id}}})])
            stencil.job_backlog.pop(0)
            await job_queue.enqueue_job(job)

    return loaded


async def startup_task():
    """Task to run at startup to initialize Arborescent jobs."""
    global _stencil_cfg
    stencil_col = orm.get_stencil_collection()
    _stencil_cfg = await  _get_stencil_config()
    async for stencildb in stencil_col.find(
        {"open_jobs": {"$exists": True, "$not": {"$size": 0}}}):
        stencil = from_dict(data_class=orm.StencilDB, data=stencildb)
        for open_job in stencil.open_jobs:
            job = ArborescentJob(
                cur_state=JobStateEnum.new,
                timestamp=datetime.now(timezone.utc),
                job_id=copy.deepcopy(open_job.job_id),
                grafting_lists=[[]],
                ACN=stencil.ACN,
                rootstock_acn=stencil.rootstock_acn,
                scion_acn=stencil.scion_acn)

            job.set_page(copy.deepcopy(open_job.cursor))
            await job_queue.enqueue_job(job)


async def set_stencils_complete():
    global _stencil_cfg
    stencil_col = orm.get_stencil_collection()
    while True:
        await asyncio.sleep(5)
        async for stencildb in stencil_col.find(
            {"job_backlog": {"$exists": True, "$size": 0},
             "open_jobs": {"$exists": True, "$size": 0},
             "state": orm.StencilStateEnum.no_headroom}):
            stencil = from_dict(data_class=orm.StencilDB, data=stencildb)
            result = await stencil_col.update_one({"_id": stencil._id},
                                                  {"$set": {
                                                      "state": orm.StencilStateEnum.complete}})


async def time_job():
    """Task to run at startup to initialize Arborescent jobs."""
    global _stencil_cfg
    while True:
        await asyncio.sleep(1)
        stencil_col = orm.get_stencil_collection()
        if _stencil_cfg.current_completed_acn < _stencil_cfg.max_acn:
            jqstats = await job_queue.get_job_statistics(ArborescentJob)
            if not await load_jobs():
                if jqstats["queue_length"] == 0:
                    complete_nonzero_stencils = await stencil_col.count_documents(
                        _complete_nonzero_stencil(_stencil_cfg.current_completed_acn + 1))
                    total_nonzero_stencils = await stencil_col.count_documents(
                        _nonzero_stencil(_stencil_cfg.current_completed_acn + 1))
                    complete_zero_stencils = await stencil_col.count_documents(
                        _complete_zero_stencil(_stencil_cfg.current_completed_acn + 1))
                    if complete_nonzero_stencils == total_nonzero_stencils:
                        await _update_stencil_zero_config()
                        await _build_zero_jobs(_stencil_cfg)
                    if 1 == complete_zero_stencils:
                        await _update_stencil_config()
                        await _build_nonzero_jobs(_stencil_cfg)
                    await load_jobs()
                    await startup_task()
