"""Interface class for acquisition parameters."""

from dataclasses import asdict, dataclass


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
    adc_samples: int = 500
    b1_scaling: float = 1.
    gradient_offset: Dimensions = Dimensions(0, 0, 0)
    fov_scaling: Dimensions = Dimensions(1, 1, 1)
    downsampling_rate: int = 400
    num_averages: int = 1

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
