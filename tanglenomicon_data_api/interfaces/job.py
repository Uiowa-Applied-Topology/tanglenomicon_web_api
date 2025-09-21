"""The Job interfaces."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class JobStateEnum(str, Enum):
    """The enum defines the states a job can take."""

    new = "new"
    pending = "pending"
    complete = "complete"
    writing = "writing"


class GenerationJobResults(BaseModel):
    """The class describes the common interface all jobResults types implement."""

    job_id: str


class ConfirmJobReceipt(GenerationJobResults):
    """The class describes the response type for jobs reported by clients."""

    accepted: bool = False


class GenerationJob(BaseModel):
    """The class describes the common interface all job types implement.

    Raises
    ------
    NotImplementedError
        Classes implementing the GenerationJob should define the interface
        functions. If the functions are not present exception should be thrown.
    """

    job_id: str
    timestamp: datetime
    cur_state: JobStateEnum = JobStateEnum.new
    client_id: str = None
    _results: GenerationJobResults

    async def store(self):
        """Interface for functions to store job results.

        Raises
        ------
        NotImplementedError
            Classes implementing the GenerationJob should define the interface
            functions. If the functions are not present exception should be thrown.
        """
        raise NotImplementedError

    def update_results(self, res: GenerationJobResults):
        """Interface for functions to update job with results.

        Parameters
        ----------
        res : generation_job_results
            The results to store with the job.

        Raises
        ------
        NotImplementedError
            Classes implementing the GenerationJob should define the interface
            functions. If the functions are not present exception should be thrown.
        """
        raise NotImplementedError