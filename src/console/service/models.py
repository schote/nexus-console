"""Definition of models for nexus service."""
from pydantic import BaseModel
# import pypulseq as pp
# from console.interfaces.acquisition_parameter import AcquisitionParameter


class Job(BaseModel):
    """Job model."""

    # sequence: str | pp.Sequence
    sequence: str
    save_unprocessed: bool = False
