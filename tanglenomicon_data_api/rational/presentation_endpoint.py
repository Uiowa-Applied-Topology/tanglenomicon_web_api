"""Defines the public API endpoints to work/report on rational tangles."""

from fastapi import Depends, APIRouter, HTTPException
from . import orm
from typing import Annotated, List
from dacite import from_dict

router = APIRouter(
    prefix="/rational",
    tags=["Rational"],
    dependencies=[],
    responses={404: {"description": "Not found"}},
)


################################################################################
# Helper Functions
################################################################################


async def _retrieve_rational_tangles(
    start_id: str = None,
    crossing_num_min: int = 0,
    page_idx: int = 0,
    page_size: int = 100,
):
    if page_size <= 0:
        raise HTTPException(status_code=404, detail="Page size must be positive")
    tangle_col = orm.get_rational_collection()
    if start_id is None:
        tangle_page = (
            await tangle_col.find(
                {"crossing_num": {"$gte": crossing_num_min}, "isRational": True}
            )
            .sort([("crossing_num", 1), ("_id", 1)])
            .limit(page_size)
            .to_list(page_size)
        )
        for i in range(page_idx):
            tangle_page = (
                await tangle_col.find(
                    {
                        "isRational": True,
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
                    "isRational": True,
                    "$or": [
                        {"crossing_num": {"$gt": crossing_num_min}},
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
    return [from_dict(data_class=orm.RationalTangDB, data=tang) for tang in tangle_page]


@router.get("/tangles", response_model=List[orm.RationalTangDB])
async def retrieve_rational_tangles(
    tangle_list: Annotated[
        List[orm.RationalTangDB], Depends(_retrieve_rational_tangles)
    ],
):
    """Return the next rational job.

    Parameters
    ----------
    tangle_list : Annotated[mj.rational_Job, Depends
        The next rational Job.

    Returns
    -------
    rational_Job
        The next rational Job.
    """
    return tangle_list
