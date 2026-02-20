"""Definition of enums."""

from enum import Enum


class DDCMethod(str, Enum):
    """Enum for DDC methods."""

    FIR = "finite-impulse-response-filter"
    AVG = "moving-average-filter"
    CIC = "cascaded-integrator-comb-filter"


class RxCommand(Enum):
    """Enum for RX card commands."""

    START = 1
    STOP = 2
    SHUTDOWN = 3


class TxCommand(Enum):
    """Enum for TX card commands."""

    START = 1
    STOP = 2
    SHUTDOWN = 3
