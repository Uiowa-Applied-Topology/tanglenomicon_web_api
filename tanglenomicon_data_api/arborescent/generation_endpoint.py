"""Defines the public API endpoints to work/report on arborescent tangles."""

from fastapi import Depends, APIRouter, HTTPException
from ..internal.security import auth_current_user, get_current_user, User
from ..interfaces.job import ConfirmJobReceipt
from . import job as aj
from ..internal import config_store, job_queue
from typing import Annotated

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
    new_arbor_j_cnt = (await job_queue.get_job_statistics(aj.ArborescentJob))["new"]
    if new_arbor_j_cnt < config_store.cfg_dict["job-queue"]["min-new-count"]:
        await aj.get_jobs(
            config_store.cfg_dict["job-queue"]["min-new-count"] - new_arbor_j_cnt
        )
    job = await job_queue.get_next_job(aj.ArborescentJob, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
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
