"""Interface class for acquisition parameters."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Dimensions:
    """Dataclass for definition of dimensional parameters."""

    x: float | int  # pylint: disable=invalid-name
    y: float | int  # pylint: disable=invalid-name
    z: float | int  # pylint: disable=invalid-name


@dataclass(slots=True, frozen=True)
class AcquisitionParameter:
    """Parameters which define an acquisition."""

    larmor_frequency: float
    b1_scaling: float
    fov_offset: Dimensions
    fov_scaling: Dimensions
    downsampling_rate: int = 200
