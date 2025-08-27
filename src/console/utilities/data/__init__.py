"""Init file."""
import logging

def get_logger() -> logging.Logger: 
    return logging.getLogger("ISMRMRD")

from .ismrmrd_1d import write_1d_mrd
from .ismrmrd_imaging import write_imaging_mrd

__all__ = [
    "write_1d_mrd",
    "write_imaging_mrd",
]