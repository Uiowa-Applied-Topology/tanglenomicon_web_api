"""Defines the public API endpoints to work/report on arborescent tangles."""

from fastapi import Depends, APIRouter, HTTPException
from . import orm, job
from ..internal import job_queue
from typing import Annotated, List
from dacite import from_dict

router = APIRouter(
    prefix="/arborescent",
    tags=["Arborescent"],
    dependencies=[],
    responses={404: {"description": "Not found"}},
)


################################################################################
# Helper Functions
################################################################################


async def _retrieve_arborescent_tangles(
    start_id: str = None,
    crossing_num_min: int = 0,
    page_idx: int = 0,
    page_size: int = 100,
):
    if page_size <= 0:
        raise HTTPException(status_code=404, detail="Page size must be positive")
    tangle_col = orm.get_arborescent_collection()
    if start_id is None:
        tangle_page = (
            await tangle_col.find(
                {"crossing_num": {"$gte": crossing_num_min}, "isArborescent": True}
            )
            .sort([("crossing_num", 1), ("_id", 1)])
            .limit(page_size)
            .to_list(page_size)
        )
        for i in range(page_idx):
            tangle_page = (
                await tangle_col.find(
                    {
                        "isArborescent": True,
                        "$or": [
                            {"crossing_num": {"$gt": tangle_page[-1]["crossing_num"]}},
                            {
                                "crossing_num": tangle_page[-1]["crossing_num"],
                                "_id": {"$gt": tangle_page[-1]["_id"]},
                            },
                        ],
                    }
                )
                .sort([("crossing_num", 1), ("_id", 1)])
                .limit(page_size)
                .to_list(page_size)
            )
    else:
        tangle_page = (
            await tangle_col.find(
                {
                    "isArborescent": True,
                    "$or": [
                        {"crossing_num": {"$gte": crossing_num_min}},
                        {
                            "crossing_num": crossing_num_min,
                            "_id": {"$gt": start_id},
                        },
                    ],
                }
            )
            .sort([("crossing_num", 1), ("_id", 1)])
            .limit(page_size)
            .to_list(page_size)
        )
    return [
        from_dict(data_class=orm.ArborescentTangleDB, data=tang) for tang in tangle_page
    ]


@router.get("/tangles", response_model=List[orm.ArborescentTangleDB])
async def retrieve_arborescent_tangles(
    tangle_list: Annotated[
        List[orm.ArborescentTangleDB], Depends(_retrieve_arborescent_tangles)
    ]
):
    """Return the next arborescent job.

    Parameters
    ----------
    tangle_list : Annotated[mj.arborescent_Job, Depends
        The next arborescent Job.

    Returns
    -------
    arborescent_Job
        The next arborescent Job.
    """
    return tangle_list


@router.get("/queue/stats")
async def retrieve_generic_job_queue_stats() -> dict:
    """Return job queue statistics for generic jobs.

    Returns
    -------
    dict
        Job queue statistics for generic jobs. Broken into:
        - Total
        - New
        - Pending
        - Complete
    """
    return await job_queue.get_job_statistics(job.ArborescentJob)
