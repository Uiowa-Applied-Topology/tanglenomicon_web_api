"""Job Queue handles the tangle generation job "queue"."""

from ..interfaces.job import GenerationJob, GenerationJobResults, JobStateEnum
from ..internal.security import User
from . import config_store

from typing import Dict, Type, List
from datetime import datetime, timezone
import asyncio
import logging

logger = logging.getLogger("uvicorn")

_job_queue: Dict[str, GenerationJob] = dict()

jq_lock: asyncio.Lock = asyncio.Lock()
task_lock: asyncio.Lock = asyncio.Lock()


async def aiterjq():
    """sdfsdfsdf."""
    for i in _job_queue:
        yield i


async def _get_count(job_type: Type[GenerationJob] = GenerationJob) -> int:
    """Get the number of jobs from the queue.

    Parameters
    ----------
    job_type : Type[generation_job], optional
        The type of job to find, by default GenerationJob.

    Returns
    -------
    int
        The count.
    """
    global jq_lock
    async with jq_lock:
        return len(
            [i async for i in aiter(aiterjq()) if isinstance(_job_queue[i], job_type)]
        )


async def _get_count_new(job_type: Type[GenerationJob] = GenerationJob) -> int:
    """Get the number of jobs from the queue in the 'new' state.

    Parameters
    ----------
    job_type : Type[generation_job], optional
        The type of job to find, by default GenerationJob.

    Returns
    -------
    int
        The count.
    """
    global jq_lock
    async with jq_lock:
        return len(
            [
                i
                async for i in aiter(aiterjq())
                if isinstance(_job_queue[i], job_type)
                   and _job_queue[i].cur_state == JobStateEnum.new
            ]
        )


async def _get_count_complete(job_type: Type[GenerationJob] = GenerationJob) -> int:
    """Get the number of jobs from the queue in the 'complete' state.

    Parameters
    ----------
    job_type : Type[generation_job], optional
        The type of job to find, by default GenerationJob.

    Returns
    -------
    int
        The count.
    """

    global jq_lock
    async with jq_lock:
        return len(
            [
                i
                async for i in aiter(aiterjq())
                if isinstance(_job_queue[i], job_type)
                   and _job_queue[i].cur_state == JobStateEnum.complete
            ]
        )


async def _get_count_pending(job_type: Type[GenerationJob] = GenerationJob) -> int:
    """Get the number of jobs from the queue in the 'pending' state.

    Parameters
    ----------
    job_type : Type[generation_job], optional
        The type of job to find, by default GenerationJob.

    Returns
    -------
    int
        The count.
    """
    global jq_lock
    async with jq_lock:
        return len(
            [
                i
                async for i in aiter(aiterjq())
                if isinstance(_job_queue[i], job_type)
                   and _job_queue[i].cur_state == JobStateEnum.pending
            ]
        )


def _is_above_time_delta(then: datetime) -> bool:
    """Check if the time between now and then is below or above threshold.

    Parameters
    ----------
    then : datetime
        The timestamp from "then".

    Returns
    -------
    bool
        ``True`` if above threshold ``False`` otherwise.
    """
    now = datetime.now(timezone.utc)
    diff = now - then
    if diff.total_seconds() >= config_store.cfg_dict["job-queue"]["clocks"]["stale"]:
        return True
    return False


async def _clean_stale_jobs():
    """Clean job queue of stale jobs."""
    global _job_queue
    global jq_lock
    global task_lock
    logger.debug("Clean stale jobs.")

    async with task_lock:
        async with jq_lock:
            items: List[GenerationJob] = [
                _job_queue[i]
                async for i in aiter(aiterjq())
                if (_is_above_time_delta(_job_queue[i].timestamp))
                   and (_job_queue[i].cur_state != JobStateEnum.complete)
                   and (_job_queue[i].cur_state != JobStateEnum.new)
            ]
            for item in items:
                item.cur_state = JobStateEnum.new


async def _clean_complete_jobs():
    """Store complete jobs into DB."""
    global _job_queue
    global jq_lock
    global task_lock
    async with task_lock:
        async with jq_lock:
            items: List[GenerationJob] = [
                _job_queue[i]
                async for i in aiter(aiterjq())
                if _job_queue[i].cur_state == JobStateEnum.complete
            ]
        logger.info(f"Storing {len(items)} jobs.")

        async with asyncio.TaskGroup() as tg:
            for item in items:
                tg.create_task(item.store())

        for item in items:
            try:
                async with jq_lock:
                    del _job_queue[item.job_id]
            except Exception as e:
                logger.error(f"Exception while processing job {item.job_id}: {e}")
                pass


async def mark_job_complete(results: GenerationJobResults, current_user: User) -> bool:
    """Mark job in queue as complete.

    Parameters
    ----------
    results : GenerationJobResults
        The reported results from the user.
    current_user : User
        The user submitting the results.

    Returns
    -------
    bool
        ``True`` if successfully marked complete ``False`` otherwise.
    """
    global _job_queue
    logger.debug("Mark job complete.")
    marked = False
    global _jq_semephore
    async with jq_lock:
        if (
            results.job_id in _job_queue
            and _job_queue[results.job_id].cur_state == JobStateEnum.pending
            and _job_queue[results.job_id].client_id == current_user.username
        ):
            job: GenerationJob = _job_queue[results.job_id]
            job.update_results(results)
            job.cur_state = JobStateEnum.complete
            marked = True
        else:
            ...
    # @@@IMPROVEMENT: should add logging here.
    return marked


async def get_next_job(
    job_type: Type[GenerationJob], current_user: User
) -> GenerationJob | None:
    """Get the next job to complete from the job queue.

    Parameters
    ----------
    job_type : Type[generation_job]
        The type of job to find in the queue.
    current_user : User
        The user requesting the job.

    Returns
    -------
    GenerationJob | None
        The job to feed the user or None if none exist.
    """
    global _job_queue
    global jq_lock
    job = None
    async with jq_lock:
        items = [
            i
            async for i in aiter(aiterjq())
            if isinstance(_job_queue[i], job_type)
               and _job_queue[i].cur_state == JobStateEnum.new
        ]
        if len(items) > 0:
            _job_queue[items[0]].cur_state = JobStateEnum.pending
            _job_queue[items[0]].client_id = current_user.username
            job = _job_queue[items[0]]
        else:
            ...
    return job


async def enqueue_job(job: GenerationJob) -> bool:
    """Add a job to the queue.

    Parameters
    ----------
    job : generation_job
        The job to add to the queue.

    Returns
    -------
    bool
        ``True`` if job is enqueued ``False`` otherwise.
    """
    global _job_queue
    global jq_lock
    enqueued = False
    async with jq_lock:
        if job.job_id not in _job_queue:
            _job_queue[job.job_id] = job
            enqueued = True
    return enqueued


async def get_job_statistics(job_type: Type[GenerationJob] = GenerationJob) -> dict:
    """Get all job statistics.

    Parameters
    ----------
    job_type : Type[GenerationJob], optional
        The type of job to find, by default GenerationJob.

    Returns
    -------
    dict
        The queue statistics for the type.
    """
    return {
        "queue_length": await _get_count(job_type),
        "new": await _get_count_new(job_type),
        "pending": await _get_count_pending(job_type),
        "complete": await _get_count_complete(job_type),
    }


async def task_clean_stale_jobs():
    """Task that periodically cleans stale jobs from the queue."""
    while True:
        await asyncio.sleep(config_store.cfg_dict["job-queue"]["clocks"]["stale"])
        await _clean_stale_jobs()


async def task_clean_complete_jobs():
    """Task that periodically stores complete jobs in the queue."""
    while True:
        await asyncio.sleep(config_store.cfg_dict["job-queue"]["clocks"]["complete"])
        await _clean_complete_jobs()
