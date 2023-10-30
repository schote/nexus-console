"""Interface class for acquisition parameters."""

from dataclasses import asdict, dataclass


@dataclass(slots=True, frozen=True)
class Dimensions:
    """Dataclass for definition of dimensional parameters."""

    x: float | int  # pylint: disable=invalid-name
    """X dimension."""

    y: float | int  # pylint: disable=invalid-name
    """Y dimension."""

    z: float | int  # pylint: disable=invalid-name
    """Z dimension."""


@dataclass(slots=True, frozen=True)
class AcquisitionParameter:
    """Parameters which define an acquisition."""

    larmor_frequency: float
    """Larmor frequency (frequency of the carrier signal) which is used for sequence unrolling."""

    adc_samples: int = 500
    """Number of adc samples after DDC."""

    b1_scaling: float = 1.0
    """Scaling of the B1 field (RF transmit power)."""

    gradient_offset: Dimensions = Dimensions(0, 0, 0)
    """Gradient offset values."""

    fov_scaling: Dimensions = Dimensions(1, 1, 1)
    """Field of view scaling factor."""

    downsampling_rate: int = 200
    """Down-sampling rate of acquired samples to raw data."""

    num_averages: int = 1
    """Number of averages."""

    def dict(self, use_strings: bool = False) -> dict:
        """Return acquisition parameters as dictionary.

        Parameters
        ----------
        use_strings, optional
            boolean flag indicating if values of dictionary should be represented as strings, by default False

        Returns
        -------
            Acquisition parameter dictionary
        """
        if use_strings:
            return {k: str(v) for k, v in asdict(self).items()}
        return asdict(self)
