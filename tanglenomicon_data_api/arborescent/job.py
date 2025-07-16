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
import uuid
from pymongo import UpdateOne
import logging
import hashlib

logger = logging.getLogger("uvicorn")

_stencil_cfg_semaphore: asyncio.Lock = asyncio.Lock()
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


def _started_stencil(acn: int):
    return {
        "$and": [
            {"state": {"$ne": orm.StencilStateEnum.complete}},
            {"state": {"$ne": orm.StencilStateEnum.new}},
            {"ACN": {"$lte": acn}},
            {"_id": {"$ne": "config"}},
        ]
    }


def _not_complete_filter(acn: int):
    return {
        "$and": [
            {"ACN": acn},
            {"state": {"$ne": orm.StencilStateEnum.complete}},
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


def _move_head(stencildb: orm.StencilDB, rootstock_count: int,
               scion_count: int) -> orm.StencilHeadStateEnum:
    """Move the head of the Stencil forward by a page.

    Parameters
    ----------
    sten : orm.arbor_stencil_db
        A stencil from the DB.

    Returns
    -------
    orm.HeadState_Enum
        Returns the current state of the stencil head. Headroom if not the last
        page was just completed or No headroom otherwise.
    """
    num_rs_pages = math.ceil(
        rootstock_count / config_store.cfg_dict["tangle-classes"]["arborescent"]["page_size"]
    )
    num_sc_pages = math.ceil(
        scion_count / config_store.cfg_dict["tangle-classes"]["arborescent"]["page_size"]
    )

    if stencildb.state == orm.StencilStateEnum.started:
        stencildb.head[0] += 1
        if num_rs_pages <= stencildb.head[0]:
            stencildb.head[0] = 0
            stencildb.head[1] += 1

        if num_sc_pages <= stencildb.head[1]:
            stencildb.head[0] = -1
            stencildb.head[1] = -1
            return orm.StencilHeadStateEnum.no_headroom
        return orm.StencilHeadStateEnum.headroom
    return None


async def _get_rootstocklist(acn: int, page: int):
    col = orm.get_arborescent_collection()
    lis_p = []
    lis_n = []
    lis_u = []
    pipeline = [
        {"$match": {"ACN": acn}},
        {
            "$facet": {
                "metadata": [{"$count": "totalCount"}],
                "data": [
                    {"$skip": int(page * config_store.cfg_dict["tangle-classes"]["arborescent"][
                        "page_size"])},
                    {"$limit": int(
                        config_store.cfg_dict["tangle-classes"]["arborescent"]["page_size"])},
                ],
            }
        },
    ]
    async for response in col.aggregate(pipeline):
        if response["metadata"][0]["totalCount"] == 0:
            raise NameError(
                "Arborescent list is empty."
            )  # @@@IMPROVEMENT: needs to be updated to exception object'

        async def ritor(data):
            for item in data:
                yield item

        tan_lis = [
            from_dict(data_class=orm.ArborescentTangleDB, data=tang) async for tang in
            ritor(response["data"])
        ]
        lis_p.extend([tang._id for tang in tan_lis if tang.positivity == "positive"])
        lis_n.extend([tang._id for tang in tan_lis if tang.positivity == "negative"])
        lis_u.extend([tang._id for tang in tan_lis if tang.positivity == "neutral"])
    return lis_p, lis_n, lis_u


async def _get_scionlist(acn: int, page: int):
    col = orm.get_arborescent_collection()
    lis_p = []
    lis_n = []
    lis_u = []
    pipeline = [
        {"$match": {"$and": [{"ACN": acn}, {"is_good": True}]}},
        {
            "$facet": {
                "metadata": [{"$count": "totalCount"}],
                "data": [
                    {"$skip": int(page * config_store.cfg_dict["tangle-classes"]["arborescent"][
                        "page_size"])},
                    {"$limit": int(config_store.cfg_dict["tangle-classes"]["arborescent"][
                                       "page_size"])},
                ],
            }
        },
    ]
    async for response in col.aggregate(pipeline):
        if response["metadata"][0]["totalCount"] == 0:
            raise NameError(
                "Arborescent list is empty."
            )  # @@@IMPROVEMENT: needs to be updated to exception object

        async def ritor(data):
            for item in data:
                yield item

        tan_lis = [
            from_dict(data_class=orm.ArborescentTangleDB, data=tang) async for tang in
            ritor(response["data"])
        ]
        lis_p.extend([tang._id for tang in tan_lis if tang.positivity == "positive"])
        lis_n.extend([tang._id for tang in tan_lis if tang.positivity == "negative"])
        lis_u.extend([tang._id for tang in tan_lis if tang.positivity == "neutral"])
        ...
    return lis_p, lis_n, lis_u


async def _build_job(rootstock_acn: int, scion_acn: int, pages: List[int], id: str,
                     job_id: str = None) -> str:
    """Build and enqueue a new Arborescent job.

    Parameters
    ----------
    stencil : List[int]
        The stencil to fill in.
    pages : List[int]
        The rational pages to retrieve.
    job_id : str, optional
        The id to use for the job, by default None

    Returns
    -------
    str
        The id for the built and enqueued job.
    """
    try:
        if not job_id:
            m = hashlib.sha256()
            m.update(id.encode("utf-8"))
            m.update(pages[0].to_bytes())
            m.update(pages[1].to_bytes())
            m.update((rootstock_acn + scion_acn).to_bytes())
            m.digest()
            job_id = m.hexdigest()

        job = ArborescentJob(
            cur_state=JobStateEnum.new,
            timestamp=datetime.now(timezone.utc),
            job_id=job_id,
            grafting_lists=[[]],
            ACN=rootstock_acn + scion_acn,
        )
        rp, rn, ru = await _get_rootstocklist(rootstock_acn, pages[0])
        sp, sn, su = await _get_scionlist(scion_acn, pages[1])
        job.grafting_lists = [
            [rp, ["positive"] * len(rp), sp, ["positive"] * len(sp)],
            [rp, ["positive"] * len(rp), su, ["neutral"] * len(su)],
            [ru, ["neutral"] * len(ru), sp, ["positive"] * len(sp)],
            [rn, ["negative"] * len(rn), sn, ["negative"] * len(sn)],
            [rn, ["negative"] * len(rn), su, ["neutral"] * len(su)],
            [ru, ["neutral"] * len(ru), sn, ["negative"] * len(sn)],
            [ru, ["neutral"] * len(ru), su, ["neutral"] * len(su)],
        ]
        await job_queue.enqueue_job(job)
    except Exception as e:
        logger.error(f"Exception while building arborescent tangle job: {e}")
        pass
    # @@@IMPROVEMENT: this need error handling.
    return job.job_id


class ArborescentJobResults(GenerationJobResults):
    """The implementation of job results for Arborescent jobs."""

    arbor_list: List[orm.ArborescentTangleDB]


class ArborescentJob(GenerationJob):
    """The implementation of job for Arborescent tangles."""

    grafting_lists: List[List[List[str]]]
    ACN: int
    _stencil: str = None
    _results: ArborescentJobResults = None
    _update_semaphore: asyncio.Lock = asyncio.Lock()

    async def _update_stencil(self):
        """Update the parent stencil."""
        stencil_col = orm.get_stencil_collection()
        async with self._update_semaphore:
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

            async def aiter_open_jobs():
                for job in stencil.open_jobs:
                    yield job

            i = [j.job_id async for j in aiter_open_jobs()].index(self.job_id)
            del stencil.open_jobs[i]
            if (
                stencil.state == orm.StencilStateEnum.no_headroom
                and len(stencil.open_jobs) == 0
            ):
                stencil.state = orm.StencilStateEnum.complete
            await stencil_col.replace_one({"_id": stencil._id}, asdict(stencil))

    async def store(self) -> bool:
        """Store the current job into the Arborescent tangle collection.

        Returns
        -------
        bool
            Indicator for success of storage.
        """
        ret_val = False
        arborescent_col = orm.get_arborescent_collection()

        async def aiter_results():
            for tang in self._results.arbor_list:
                yield tang

        tangles_2_store = [
            UpdateOne(
                {"_id": str(tang._id)},
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
        tangles_2_store.extend([
            UpdateOne(
                {"_id": str(tang._id)},
                {"$push": {"parents": [rs_set[0], rs_set[1]]}},
                upsert=True,
            )
            async for tang in aiter_results() for rs_set in tang.parents
        ])

        if len(tangles_2_store) > 0:
            ret_val = True
            try:
                await arborescent_col.bulk_write(tangles_2_store)
                await self._update_stencil()

            except Exception as e:
                logger.error(f"Exception while storing arborescent tangles: {e}")
                ret_val = False
                pass
        return ret_val

    def update_results(self, res: ArborescentJobResults):
        """Update the job with the reported results."""
        self._results = res


async def _get_nonzero_jobs(stencil_cfg: orm.StencilCfg, count: int = 1):
    """Get and build a specified number of jobs.

    Parameters
    ----------
    count : int, optional
        The number of jobs to get and build, by default 1
    """
    stencil_col = orm.get_stencil_collection()
    try:
        stencildb = await stencil_col.find_one(
            _open_nonzero_stencil(stencil_cfg.current_completed_acn + 1))
        if stencildb:
            stencil = from_dict(
                data_class=orm.StencilDB,
                data=stencildb,
            )
            if stencil.state == orm.StencilStateEnum.new:
                job_id = await _build_job(stencil.rootstock_acn, stencil.scion_acn,
                                          stencil.head, str(stencil._id))
                stencil.open_jobs.append(
                    orm.StencilJobDB(job_id=job_id, cursor=copy.deepcopy(stencil.head))
                )
            stencil.state = orm.StencilStateEnum.started
            while count > 0:
                count -= 1
                if _move_head(stencil, stencil_cfg.current_counts[stencil.rootstock_acn],
                              stencil_cfg.current_good_counts[
                                  stencil.scion_acn]) == orm.StencilHeadStateEnum.no_headroom:
                    stencil.state = orm.StencilStateEnum.no_headroom
                    break
                job_id = await _build_job(stencil.rootstock_acn, stencil.scion_acn,
                                          stencil.head, str(stencil._id))
                stencil.open_jobs.append(
                    orm.StencilJobDB(job_id=job_id, cursor=copy.deepcopy(stencil.head))
                )

            await stencil_col.replace_one({"_id": stencil._id}, asdict(stencil))
    except Exception as e:
        logger.error(f"Exception while obtaining arborescent jobs: {e}")
        ...


async def _get_zero_job(stencil_cfg: orm.StencilCfg, count: int):
    """Get and build a specified number of jobs.

    Parameters
    ----------
    count : int, optional
        The number of jobs to get and build, by default 1
    """
    stencil_col = orm.get_stencil_collection()
    try:
        if stencildb := await stencil_col.find_one(
            _open_zero_stencil(stencil_cfg.current_completed_acn + 1)):
            stencil = from_dict(
                data_class=orm.StencilDB,
                data=stencildb,
            )
            if stencil.state == orm.StencilStateEnum.new:
                job_id = await _build_job(stencil.rootstock_acn, stencil.scion_acn,
                                          stencil.head, str(stencil._id))
                stencil.open_jobs.append(
                    orm.StencilJobDB(job_id=job_id, cursor=copy.deepcopy(stencil.head))
                )
                stencil.state = orm.StencilStateEnum.started
            while count > 0:
                count -= 1
                if _move_head(stencil, stencil_cfg.current_counts[stencil.rootstock_acn],
                              stencil_cfg.current_good_counts[
                                  stencil.scion_acn]) == orm.StencilHeadStateEnum.no_headroom:
                    stencil.state = orm.StencilStateEnum.no_headroom
                    break

                job_id = await _build_job(stencil.rootstock_acn, stencil.scion_acn,
                                          stencil.head, str(stencil._id))
                stencil.open_jobs.append(
                    orm.StencilJobDB(job_id=job_id, cursor=copy.deepcopy(stencil.head))
                )

            await stencil_col.replace_one({"_id": stencil._id}, asdict(stencil))
    except Exception as e:
        logger.error(f"Exception while obtaining jobs: {e}")
        ...


async def get_jobs(count: int = 1):
    global _stencil_cfg
    global _debounce
    if _debounce:
        if _debounce - datetime.now() > timedelta(seconds=1):
            _debounce = None
    else:
        _debounce = datetime.now()

    stencil_col = orm.get_stencil_collection()
    if _stencil_cfg.current_completed_acn < _stencil_cfg.max_acn:
        open_count = await stencil_col.count_documents(
            _not_complete_filter(_stencil_cfg.current_completed_acn + 1))
        if 0 == open_count:
            await _update_stencil_config()
        if 1 == open_count:
            await _update_stencil_zero_config()
            await _get_zero_job(_stencil_cfg, count)
        else:
            await _get_nonzero_jobs(_stencil_cfg, count)


async def startup_task():
    """Task to run at startup to initialize Arborescent jobs."""
    global _stencil_cfg
    stencil_col = orm.get_stencil_collection()
    _stencil_cfg = await  _get_stencil_config()
    async with _stencil_cfg_semaphore:
        async for stencildb in stencil_col.find(
            _started_stencil(_stencil_cfg.current_completed_acn + 1)):
            stencil = from_dict(data_class=orm.StencilDB, data=stencildb)

            async def aiter_open_jobs():
                for open_item in stencil.open_jobs:
                    yield open_item

            async for open_item in aiter_open_jobs():
                await _build_job(stencil.rootstock_acn, stencil.scion_acn,
                                 stencil.head, str(stencil._id),
                                 job_id=open_item.job_id
                                 )
                ...
            ...
    new_arbor_j_cnt = (await job_queue.get_job_statistics(ArborescentJob))["new"]
    if new_arbor_j_cnt < config_store.cfg_dict["job-queue"]["min-new-count"]:
        await  _update_stencil_zero_config()
        await get_jobs(config_store.cfg_dict["job-queue"]["min-new-count"] - new_arbor_j_cnt)
        ...


async def time_job():
    """Task to run at startup to initialize Arborescent jobs."""
    while True:
        await asyncio.sleep(1)
        await get_jobs(config_store.cfg_dict["job-queue"]["min-new-count"])
        ...
