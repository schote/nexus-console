"""Definition of models for nexus service."""
from pydantic import BaseModel
from asyncio import Event
from dataclasses import dataclass
# import pypulseq as pp
# from console.interfaces.acquisition_parameter import AcquisitionParameter


class ScanRequest(BaseModel):
    """Job model."""

    sequence: str
    save_unprocessed: bool = False


@dataclass
class Job:
    request: ScanRequest
    event: Event | None
    status: str = "created"
    result: str | None = None


