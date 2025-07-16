"""An implementation of the job interface for Montesinos jobs."""

from datetime import datetime, timezone
from ..interfaces.job import GenerationJob, GenerationJobResults, JobStateEnum
from ..internal import config_store, job_queue
from . import orm
from ..rational import orm as rat_orm
from typing import List
from dacite import from_dict
from dataclasses import asdict
import math
import copy
import uuid
from pymongo import UpdateOne
import logging

logger = logging.getLogger("uvicorn")

OPEN_STEN_FILTER = {
    "$and": [
        {"state": {"$ne": orm.StencilStateEnum.complete}},
        {"state": {"$ne": orm.StencilStateEnum.no_headroom}},
    ]
}
STARTED_STEN_FILTER = {
    "$and": [
        {"state": {"$ne": orm.StencilStateEnum.complete}},
        {"state": {"$ne": orm.StencilStateEnum.new}},
    ]
}


def _move_head(stencildb: orm.StencilDB) -> orm.StencilHeadStateEnum:
    """Move the head of the Stencil forward by a page.

    Parameters
    ----------
    sten : orm.mont_stencil_db
        A stencil from the DB.

    Returns
    -------
    orm.HeadState_Enum
        Returns the current state of the stencil head. Headroom if not the last
        page was just completed or No headroom otherwise.
    """
    overflow = True
    for i, sten_entry in enumerate(stencildb.stencil_array):
        if overflow:
            stencildb.head[i] += 1
            overflow = False
        if (
            max(
                0,
                (
                    sten_entry
                    - 2
                    - config_store.cfg_dict["tangle-classes"]["montesinos"]["page-exp"]
                ),
            )
            < stencildb.head[i]
        ):
            stencildb.head[i] = 0
            overflow = True
        else:
            break
    if overflow:
        for i, sten_entry in enumerate(stencildb.stencil_array):
            stencildb.head[i] = sten_entry
        return orm.StencilHeadStateEnum.no_headroom
    return orm.StencilHeadStateEnum.headroom


async def _build_job(stencil: List[int], pages: List[int], job_id: str = None) -> str:
    """Build and enqueue a new Montesinos job.

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
    rational_col = rat_orm.get_rational_collection()
    if not job_id:
        job_id = str(uuid.uuid4())
    crossing_num = 0
    for cn in stencil:
        crossing_num += cn
    job = MontesinosJob(
        cur_state=JobStateEnum.new,
        timestamp=datetime.now(timezone.utc),
        crossing_num=crossing_num,
        job_id=job_id,
        rat_lists=list(),
    )
    job.stencil = " ".join(map(str, stencil))
    for cn, page in zip(stencil, pages):
        lis = []
        pipeline = [
            {
                "$match": {
                    "$and": [
                        {"crossing_num": cn},
                        {"in_unit_interval": True},
                        {"isRational": True},
                    ]
                }
            },
            {
                "$facet": {
                    "metadata": [{"$count": "totalCount"}],
                    "data": [
                        {
                            "$skip": int(
                                page
                                * math.pow(
                                    2,
                                    config_store.cfg_dict["tangle-classes"][
                                        "montesinos"
                                    ]["page-exp"],
                                )
                            )
                        },
                        {
                            "$limit": int(
                                math.pow(
                                    2,
                                    config_store.cfg_dict["tangle-classes"][
                                        "montesinos"
                                    ]["page-exp"],
                                )
                            )
                        },
                    ],
                }
            },
        ]
        async for response in rational_col.aggregate(pipeline):
            if response["metadata"]:
                if response["metadata"][0]["totalCount"] == 0:
                    raise NameError(
                        "Rational list is empty."
                    )  # @@@IMPROVEMENT: needs to be updated to exception object
                lis.extend(
                    [
                        from_dict(data_class=rat_orm.RationalTangDB, data=rat_tang)._id
                        for rat_tang in response["data"]
                    ]
                )
            ...

        job.rat_lists.append(lis)
    await job_queue.enqueue_job(job)
    # @@@IMPROVEMENT: this need error handling.
    return job.job_id


class MontesinosJobResults(GenerationJobResults):
    """The implementation of job results for Montesinos jobs."""

    mont_list: List[str]


class MontesinosJob(GenerationJob):
    """The implementation of job for Montesinos tangles."""

    rat_lists: List[List[str]]
    crossing_num: int
    _stencil: str = None
    _results: MontesinosJobResults = None

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
        """Store the current job into the Montesinos tangle collection.

        Returns
        -------
        bool
            Indicator for success of storage.
        """
        ret_val = False
        montesinos_col = orm.get_montesinos_collection()

        async def aiter_results():
            for tang in list(set(self._results.mont_list)):
                yield tang

        tangles_2_store = [
            UpdateOne(
                {"_id": str(tang)},
                {
                    "$set": {
                        "crossing_num": int(self.crossing_num),
                        "parent_stencil": str(self.stencil),
                        "isMontesinos": True,
                    }
                },
                upsert=True,
            )
            async for tang in aiter_results()
        ]
        if len(tangles_2_store) > 0:
            ret_val = True
            try:
                await montesinos_col.bulk_write(tangles_2_store)
                await self._update_stencil()
            except Exception as e:
                logger.error(f"Exception while storing montesinos tangles: {e}")
                ret_val = False
                pass
        return ret_val

    @property
    def stencil(self) -> str:
        """Return the parent stencil.

        Returns
        -------
        The parent stencil.
        """
        return self._stencil

    @stencil.setter
    def stencil(self, value):
        """Set the parent stencil."""
        self._stencil = value

    def update_results(self, res: MontesinosJobResults):
        """Update the job with the reported results."""
        self._results = res


async def get_jobs(count: int = 1):
    """Get and build a specified number of jobs.

    Parameters
    ----------
    count : int, optional
        The number of jobs to get and build, by default 1
    """
    stencil_col = orm.get_stencil_collection()
    try:
        stencildb = await stencil_col.find_one(OPEN_STEN_FILTER)
        if stencildb:
            stencil = from_dict(
                data_class=orm.StencilDB,
                data=stencildb,
            )
            stencil.state = orm.StencilStateEnum.started
            while count > 0 and stencil:
                job_id = await _build_job(stencil.stencil_array, stencil.head)
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
    """Task to run at startup to initialize Montesinos jobs."""
    stencil_col = orm.get_stencil_collection()

    async for stencildb in stencil_col.find(STARTED_STEN_FILTER):
        stencildb = from_dict(data_class=orm.StencilDB, data=stencildb)

        async def aiter_open_jobs():
            for open_item in stencildb.open_jobs:
                yield open_item

        async for open_item in aiter_open_jobs():
            await _build_job(
                stencildb.stencil_array, open_item.cursor, job_id=open_item.job_id
            )
            ...
    new_mont_j_cnt = (await job_queue.get_job_statistics(MontesinosJob))["new"]
    if new_mont_j_cnt < config_store.cfg_dict["job-queue"]["min-new-count"]:
        await get_jobs(
            config_store.cfg_dict["job-queue"]["min-new-count"] - new_mont_j_cnt
        )
