"""Defines the public API endpoints to work/report on arborescent tangles."""

from fastapi import Depends, APIRouter, HTTPException
from ..internal.security import auth_current_user, get_current_user, User
from ..interfaces.job import ConfirmJobReceipt
from . import job as aj
from ..internal import config_store, job_queue
from typing import Annotated
import asyncio

_arbor_job_get_semaphore: asyncio.Lock = asyncio.Lock()

router = APIRouter(
    prefix="/arborescent",
    tags=["Arborescent"],
    dependencies=[Depends(auth_current_user)],
    responses={404: {"description": "Not found"}},
)


################################################################################
# Helper Functions
################################################################################


async def _report_job_results(
    job_results: aj.ArborescentJobResults,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConfirmJobReceipt:
    """Return a confirmation or denial for job results.

    Parameters
    ----------
    job_results : aj.Arborescent_Job_Results
        The job results reported by a client.
    current_user : Annotated[User, Depends
        The user reporting the results.

    Returns
    -------
    confirm_job_receipt
        Either a confirmation or denial for a reported job result.

    Raises
    ------
    HTTPException
        Raise a 404 if the job isn't in the queue.
    """
    if not (await job_queue.mark_job_complete(job_results, current_user)):
        raise HTTPException(
            status_code=404, detail="Job not in queue or Job not in pending."
        )
    results = ConfirmJobReceipt(job_id=job_results.job_id, accepted=True)
    return results


async def _get_next_arborescent_job(
    current_user: Annotated[User, Depends(get_current_user)]
) -> aj.ArborescentJob:
    """Return the next arborescent job from the job queue.

    Parameters
    ----------
    current_user : Annotated[User, Depends
        The verified user requesting a job.

    Returns
    -------
    aj.Arborescent_Job
        The next Arborescent Job

    Raises
    ------
    HTTPException
        If no job found raise 404.
    """
    job = await job_queue.get_next_job(aj.ArborescentJob, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    rp, rn, ru = await aj.get_rootstocklist(job.rootstock_acn, job.page[0])
    sp, sn, su = await aj.get_scionlist(job.scion_acn, job.page[1])
    job.grafting_lists = [
        [rp, ["positive"] * len(rp), sp, ["positive"] * len(sp)],
        [rp, ["positive"] * len(rp), su, ["neutral"] * len(su)],
        [ru, ["neutral"] * len(ru), sp, ["positive"] * len(sp)],
        [rn, ["negative"] * len(rn), sn, ["negative"] * len(sn)],
        [rn, ["negative"] * len(rn), su, ["neutral"] * len(su)],
        [ru, ["neutral"] * len(ru), sn, ["negative"] * len(sn)],
        [ru, ["neutral"] * len(ru), su, ["neutral"] * len(su)],
    ]
    return job


@router.post("/job")
async def report_arborescent_job(
    response: Annotated[ConfirmJobReceipt, Depends(_report_job_results)],
) -> ConfirmJobReceipt:
    """Return the job from a client.

    Parameters
    ----------
    response : Annotated[confirm_job_receipt, Depends
        The confirmation state of the reported job.

    Returns
    -------
    confirm_job_receipt
        The confirmation state of the reported job.
    """
    return response


@router.get("/job", response_model=aj.ArborescentJob)
async def retrieve_arborescent_job(
    next_job: Annotated[aj.ArborescentJob, Depends(_get_next_arborescent_job)]
):
    """Return the next arborescent job.

    Parameters
    ----------
    next_job : Annotated[aj.Arborescent_Job, Depends
        The next Arborescent Job.

    Returns
    -------
    Arborescent_Job
        The next Arborescent Job.
    """
    return next_job
