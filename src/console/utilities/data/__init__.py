"""Init file."""
import logging

def get_logger() -> logging.Logger: 
    return logging.getLogger("ISMRMRD")

from .write_acquisition_to_mrd import write_acquisition_to_mrd
from .mrd_helper import get_nexus_acquisition_system, set_mrd_counters

__all__ = [
    "write_acquisition_to_mrd",
    "get_nexus_acquisition_system",
    "set_mrd_counters"
]