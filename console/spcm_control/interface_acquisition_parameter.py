"""Interface class for acquisition parameters."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Dimensions:
    x: float | int
    y: float | int
    z: float | int
    

@dataclass(slots=True, frozen=True)
class AcquisitionParameter:
    larmor_frequency: float
    b1_scaling: float
    fov_offset: Dimensions
    fov_scaling: Dimensions
    downsampling_rate: int = 200
    