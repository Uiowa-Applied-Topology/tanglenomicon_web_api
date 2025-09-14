"""Defines the public API endpoints to work/report on montesinos tangles."""

from fastapi import Depends, APIRouter, HTTPException
from ..internal.security import auth_current_user, get_current_user, User
from ..interfaces.job import ConfirmJobReceipt
from . import job as mj
from ..internal import config_store, job_queue
from typing import Annotated

router = APIRouter(
    prefix="/montesinos",
    tags=["Montesinos"],
    dependencies=[Depends(auth_current_user)],
    responses={404: {"description": "Not found"}},
)


################################################################################
# Helper Functions
################################################################################


async def _report_job_results(
    job_results: mj.MontesinosJobResults,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConfirmJobReceipt:
    """Return a confirmation or denial for job results.

    Parameters
    ----------
    job_results : mj.Montesinos_Job_Results
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


async def _get_next_montesinos_job(
    current_user: Annotated[User, Depends(get_current_user)],
) -> mj.MontesinosJob:
    """Return the next montesinos job from the job queue.

    Parameters
    ----------
    current_user : Annotated[User, Depends
        The verified user requesting a job.

    Returns
    -------
    mj.Montesinos_Job
        The next Montesinos Job

    Raises
    ------
    HTTPException
        If no job found raise 404.
    """
    new_mont_j_cnt = (await job_queue.get_job_statistics(mj.MontesinosJob))["new"]
    if new_mont_j_cnt < config_store.cfg_dict["job-queue"]["min-new-count"]:
        await mj.get_jobs(
            config_store.cfg_dict["job-queue"]["min-new-count"] - new_mont_j_cnt
        )
    job = await job_queue.get_next_job(mj.MontesinosJob, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("/job")
async def report_montesinos_job(
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


@router.get("/job", response_model=mj.MontesinosJob)
async def retrieve_montesinos_job(
    next_job: Annotated[mj.MontesinosJob, Depends(_get_next_montesinos_job)],
):
    """Return the next montesinos job.

    Parameters
    ----------
    next_job : Annotated[mj.Montesinos_Job, Depends
        The next Montesinos Job.

    Returns
    -------
    Montesinos_Job
        The next Montesinos Job.
    """
    return next_job
