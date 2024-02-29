"""Interface class for acquisition parameters."""

import copy
import os
import pickle
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from console.interfaces.interface_dimensions import Dimensions

STATE_FILE: str = os.path.join(Path.home(), "spcm-console/acq-parameter-state.pkl")


@dataclass(frozen=True)
class AcquisitionParameter:
    """
    Parameters to define an acquisition.

    The acquisition parameters are defined as a frozen dataclass, i.e. they are immutable.
    This makes acquisition parameters hashable, which makes it easier to recognize any changes.
    Can be updated using `dataclasses.replace(instance, larmor_frequency=2.1e6)`.
    """

    larmor_frequency: float = 2e6
    """Larmor frequency in MHz."""

    b1_scaling: float = 1.0
    """Scaling of the B1 field (RF transmit power)."""

    gradient_offset: Dimensions = Dimensions(0, 0, 0)
    """Gradient offset values in mV."""

    fov_scaling: Dimensions = Dimensions(1, 1, 1)
    """Field of view scaling for Gx, Gy and Gz."""

    decimation: int = 200
    """Decimation rate for initial down-sampling step."""

    num_averages: int = 1
    """Number of acquisition averages."""

    averaging_delay: float = 0.0
    """Delay in seconds between acquisition averages."""

    def __post_init__(self) -> None:
        """Save state after initialization.

        Class is immutable, that means a new object is created for any update of the values.
        By calling the save method after initialization, updates are automatically saved as latest state.
        """
        self.save()

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

    def save(self, file_path: str = STATE_FILE) -> None:
        """Save current acquisition parameter state.

        Parameters
        ----------
        file_path, optional
            Path to the pickle state file, by default "acq-param-state.pkl"
        """
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as file:
            pickle.dump(self.__dict__, file)

    @classmethod
    def load(cls, file_path: str = STATE_FILE) -> "AcquisitionParameter":
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

    def copy(self) -> "AcquisitionParameter":
        """Create a deepcopy of the acquisition parameters."""
        return copy.deepcopy(self)

    def update(self, /, **changes) -> "AcquisitionParameter":
        """Create a modified version and return it as new acquisition parameter object.

        Takes any keyword argument, must be attribute of acquisition parameter object.
        Wrapper for `dataclasses.replace()`.

        Example
        -------
        params = AcquisitionParameter()
        new_params = params.update(larmor_frequency=2.1e6)

        Returns
        -------
            Returns a new acquisition parameter object with a new hash
        """
        return replace(self, **changes)

    def get_hash(self) -> int:
        """Return acquisition parameter integer hash."""
        return self.__hash__()
