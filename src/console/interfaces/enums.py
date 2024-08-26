"""Definition of enums."""
from enum import Enum


class DDCMethod(str, Enum):
    """Enum for DDC methods."""

    FIR = "finite-impulse-response-filter"
    AVG = "moving-average-filter"
    CIC = "cascaded-integrator-comb-filter"
