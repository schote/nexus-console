"""Definition of models for nexus service."""
from pydantic import BaseModel
from pypulseq.Sequence import Sequence


class Job(BaseModel):
    """Job model."""

    sequence: str | Sequence
    save_unprocessed: bool = False
