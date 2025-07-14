"""An implementation of the job interface for Arborescent jobs."""

from datetime import datetime, timezone
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

logger = logging.getLogger("uvicorn")

_stencil_cfg: orm.StencilCfg = None


def _next_open_zero_stencil(acn: int):
    return {"$and": [
        {"state": {"$ne": orm.StencilStateEnum.complete}},
        {"state": {"$ne": orm.StencilStateEnum.no_headroom}},
        {"ACN": {"$lte": acn}},
        {"rootstock_acn": 0},
        {"_id": {"$ne": "config"}},
    ]
    }


def _next_nonzero_open_stencil(acn: int):
    return {
        "$and": [
            {"state": orm.StencilStateEnum.new},
            {"ACN": {"$lte": acn}},
            {"rootstock_acn": {"$ne": 0}},
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
    stencil_col = orm.get_stencil_collection()
    arbor_col = orm.get_arborescent_collection()
    _stencil_cfg.current_good_counts[
        _stencil_cfg.current_completed_acn + 1
        ] = await arbor_col.count_documents(
        {"$and": [{"ACN": _stencil_cfg.current_completed_acn + 1}, {"is_good": True}]}
    )
    await stencil_col.replace_one({"_id": _stencil_cfg._id}, asdict(_stencil_cfg))


def _move_head(stencildb: orm.StencilDB, stencilcfg: orm.StencilCfg) -> orm.StencilHeadStateEnum:
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
        stencilcfg.current_counts[stencildb.rootstock_acn]
        / config_store.cfg_dict["tangle-classes"]["arborescent"]["page_size"]
    )
    num_sc_pages = math.ceil(
        stencilcfg.current_good_counts[stencildb.scion_acn]
        / config_store.cfg_dict["tangle-classes"]["arborescent"]["page_size"]
    )

    if num_rs_pages <= stencildb.head[0]:
        stencildb.head[0] += 1

    if num_sc_pages <= stencildb.head[1]:
        stencildb.head[0] = 0
        stencildb.head[1] += 1
    else:
        return orm.StencilHeadStateEnum.no_headroom
    return orm.StencilHeadStateEnum.headroom


async def _get_rootstocklist(acn: int, page: int):
    col = orm.get_tangle_collection()
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
            )  # @@@IMPROVEMENT: needs to be updated to exception object
        tan_lis = [
            from_dict(data_class=orm.ArborescentTangleDB, data=tang) for tang in response["data"]
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
        tan_lis = [
            from_dict(data_class=orm.ArborescentTangleDB, data=tang) for tang in response["data"]
        ]
        lis_p.extend([tang._id for tang in tan_lis if tang.positivity == "positive"])
        lis_n.extend([tang._id for tang in tan_lis if tang.positivity == "negative"])
        lis_u.extend([tang._id for tang in tan_lis if tang.positivity == "neutral"])
        ...
    return lis_p, lis_n, lis_u


async def _build_job(
    acn: List[int], pages: List[int], job_id: str = None
) -> str:
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
    if not job_id:
        job_id = str(uuid.uuid4())
    job = ArborescentJob(
        cur_state=JobStateEnum.new,
        timestamp=datetime.now(timezone.utc),
        job_id=job_id,
        grafting_lists=list(),
    )
    rp, rn, ru = _get_rootstocklist(acn[0], pages[0])
    sp, sn, su = _get_scionlist(acn[1], pages[1])
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
    # @@@IMPROVEMENT: this need error handling.
    return job.job_id


class ArborescentJobResults(GenerationJobResults):
    """The implementation of job results for Arborescent jobs."""

    arbor_list: List[orm.ArborescentTangleDB]


class ArborescentJob(GenerationJob):
    """The implementation of job for Arborescent tangles."""

    grafting_lists: List[List[List[str]]]
    _stencil: str = None
    _results: ArborescentJobResults = None

    async def _update_stencil(self):
        """Update the parent stencil."""
        stencil_col = orm.get_stencil_collection()
        stencildb = from_dict(
            data_class=orm.StencilDB,
            data=(await stencil_col.find_one({"open_jobs.job_id": self.job_id})),
        )

        async def aiter_open_jobs():
            for job in stencildb.open_jobs:
                yield job

        i = [j.job_id async for j in aiter_open_jobs()].index(self.job_id)
        del stencildb.open_jobs[i]
        if (
            stencildb.state == orm.StencilStateEnum.no_headroom
            and len(stencildb.open_jobs) == 0
        ):
            stencildb.state = orm.StencilStateEnum.complete
        await stencil_col.replace_one({"_id": stencildb._id}, asdict(stencildb))

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
                        "is_good": str(tang.is_good),
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
                {"$push": {"parents": str(tang.parents)}},
                upsert=True,
            )
            async for tang in aiter_results()
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


async def get_jobs(acn: int, count: int = 1):
    """Get and build a specified number of jobs.

    Parameters
    ----------
    count : int, optional
        The number of jobs to get and build, by default 1
    """
    stencil_col = orm.get_stencil_collection()
    try:
        stencildb = await stencil_col.find_one(_next_nonzero_open_stencil(acn))
        if stencildb:
            stencil = from_dict(
                data_class=orm.StencilDB,
                data=stencildb,
            )
            stencil.state = orm.StencilStateEnum.started
            while count > 0 and stencil:
                job_id = await _build_job([stencil.rootstock_acn, stencil.scion_acn], stencil.head)
                stencil.open_jobs.append(
                    {"job_id": job_id, "cursor": copy.deepcopy(stencil.head)}
                )
                count -= 1
                if _move_head(stencil) == orm.StencilHeadStateEnum.no_headroom:
                    stencil.state = orm.StencilStateEnum.no_headroom
                    await stencil_col.replace_one({"_id": stencil._id}, asdict(stencil))
                    if stencildb := await stencil_col.find_one(OPEN_STEN_FILTER):
                        stencil = from_dict(
                            data_class=orm.StencilDB,
                            data=stencildb,
                        )
                        stencil.state = orm.StencilStateEnum.started
                    else:
                        break
            await stencil_col.replace_one({"_id": stencil._id}, asdict(stencil))
    except Exception as e:
        logger.error(f"Exception while obtaining jobs: {e}")
        ...


async def startup_task():
    """Task to run at startup to initialize Arborescent jobs."""
    global _stencil_cfg
    stencil_col = orm.get_stencil_collection()
    _stencil_cfg = await  _get_stencil_config()
    await  _update_stencil_zero_config()
    await  _update_stencil_config()
    async for stencildb in stencil_col.find(_next_open_zero_stencil(_stencil_cfg.current_completed_acn)):
        stencildb = from_dict(data_class=orm.StencilDB, data=stencildb)

        async def aiter_open_jobs():
            for open_item in stencildb.open_jobs:
                yield open_item

        async for open_item in aiter_open_jobs():
            await _build_job(
                _stencil_cfg.current_completed_acn, open_item.cursor, job_id=open_item.job_id
            )
            ...
    new_arbor_j_cnt = (await job_queue.get_job_statistics(ArborescentJob))["new"]
    if new_arbor_j_cnt < config_store.cfg_dict["job-queue"]["min-new-count"]:
        await get_jobs(_stencil_cfg.current_completed_acn,
                       config_store.cfg_dict["job-queue"]["min-new-count"] - new_arbor_j_cnt
                       )
        ...
