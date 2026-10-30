"""Definition of enums."""
from enum import StrEnum


class DDCMethod(StrEnum):
    """Enum for DDC methods."""

    FIR = "finite-impulse-response-filter"
    AVG = "moving-average-filter"
    CIC = "cascaded-integrator-comb-filter"
