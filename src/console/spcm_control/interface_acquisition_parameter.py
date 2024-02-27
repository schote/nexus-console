"""Interface class for acquisition parameters."""

import pickle
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Dimensions:
    """Dataclass for definition of dimensional parameters."""

    x: float | int  # pylint: disable=invalid-name
    """X dimension."""

    y: float | int  # pylint: disable=invalid-name
    """Y dimension."""

    z: float | int  # pylint: disable=invalid-name
    """Z dimension."""


@dataclass(frozen=True)
class AcquisitionParameter:
    """
    Parameters which define an acquisition.

    Is defined as frozen dataclass to have hashable acquisition parameters.
    Can be updated using `dataclasses.replace(instance, larmor_frequency=2.1e6)`.
    """

    larmor_frequency: float = 2e6
    """Larmor frequency in MHz."""

    b1_scaling: float = 1.0
    """Scaling of the B1 field (RF transmit power)."""

    gradient_offset: Dimensions = Dimensions(0, 0, 0)
    """Gradient offset values."""

    fov_scaling: Dimensions = Dimensions(1, 1, 1)
    """Field of view scaling for Gx, Gy and Gz."""

    decimation: int = 200
    """Decimation rate for initial down-sampling step."""

    num_averages: int = 1
    """Number of acquisition averages."""

    averaging_delay: float = 0.0
    """Delay in seconds between acquisition averages."""

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

    def save(self, file_path: str = "acq-param-state.pkl") -> None:
        """Save current acquisition parameter state.

        Parameters
        ----------
        file_path, optional
            Path to the pickle state file, by default "acq-param-state.pkl"
        """
        with open(file_path, "wb") as file:
            pickle.dump(self.__dict__, file)

    @classmethod
    def load(cls, file_path: str = "acq-param-state.pkl") -> "AcquisitionParameter":
        """Load acquisition parameter state from state file and return AcquisitionParameter instance.

        Parameters
        ----------
        file_path, optional
            Path to the pickle state file, by default "acq-param-state.pkl"
        """
        with open(file_path, "rb") as file:
            state = pickle.load(file)  # noqa: S301
        # self.__dict__.update(state)
        return cls(**state)
