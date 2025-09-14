"""Defines the public API endpoints to work/report on generic tangles."""

from fastapi import Depends, APIRouter, HTTPException
from . import orm
from ..internal import job_queue
from typing import Annotated, List
from dacite import from_dict

router = APIRouter(
    tags=["Generic"],
    dependencies=[],
    responses={404: {"description": "Not found"}},
)


################################################################################
# Helper Functions
################################################################################


async def _retrieve_generic_tangles(
    start_id: str = None,
    crossing_num_min: int = 0,
    page_idx: int = 0,
    page_size: int = 100,
):
    if page_size <= 0:
        raise HTTPException(status_code=404, detail="Page size must be positive")
    tangle_col = orm.get_generic_collection()
    if start_id is None:
        tangle_page = (
            await tangle_col.find({"crossing_num": {"$gte": crossing_num_min}})
            .sort([("crossing_num", 1), ("_id", 1)])
            .limit(page_size)
            .to_list(page_size)
        )
        for i in range(page_idx):
            tangle_page = (
                await tangle_col.find(
                    {
                        "$or": [
                            {"crossing_num": {"$gt": tangle_page[-1]["crossing_num"]}},
                            {
                                "crossing_num": tangle_page[-1]["crossing_num"],
                                "_id": {"$gt": tangle_page[-1]["_id"]},
                            },
                        ]
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
                    "$or": [
                        {"crossing_num": {"$gt": crossing_num_min}},
                        {
                            "crossing_num": crossing_num_min,
                            "_id": {"$gt": start_id},
                        },
                    ]
                }
            )
            .sort([("crossing_num", 1), ("_id", 1)])
            .limit(page_size)
            .to_list(page_size)
        )
    return [from_dict(data_class=orm.GenericTangDB, data=tang) for tang in tangle_page]


async def _retrieve_generic_tangle(id: str):
    tangle_col = orm.get_generic_collection()
    tang = await tangle_col.find_one({"_id": str(id)})
    if not tang:
        raise HTTPException(status_code=404, detail="Tangle not found.")
    return tang


@router.get("/tangles", response_model=List[orm.GenericTangDB])
async def retrieve_generic_tangles(
    tangle_list: Annotated[List[orm.GenericTangDB], Depends(_retrieve_generic_tangles)],
):
    """Return the next generic job.

    Parameters
    ----------
    tangle_list : Annotated[mj.generic_Job, Depends
        The next generic Job.

    Returns
    -------
    generic_Job
        The next generic Job.
    """
    return tangle_list


@router.get("/tangle")
async def retrieve_generic_tangle(
    tangle: Annotated[orm.GenericTangDB, Depends(_retrieve_generic_tangle)],
):
    """Return the next generic job.

    Parameters
    ----------
    tangle : Dict
        The next generic Job.

    Returns
    -------
    generic_Job
        The next generic Job.
    """
    return tangle


@router.get("/queue_stats")
async def retrieve_job_statistics(
    stats: Annotated[dict, Depends(job_queue.get_job_statistics)],
) -> dict:
    """Request for queue statistics.

    Parameters
    ----------
    stats : Annotated[dict, Depends
        The statistics.

    Returns
    -------
    dict
        The statistics.
    """
    return stats
