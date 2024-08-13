"""Interface class for acquisition parameters."""

import json
import os
import pickle  # noqa: S403
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from console.interfaces.dimensions import Dimensions
from console.interfaces.enums import DDCMethod


@dataclass(unsafe_hash=True)
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

    ddc_method: DDCMethod = DDCMethod.FIR

    num_averages: int = 1
    """Number of acquisition averages."""

    averaging_delay: float = 0.0
    """Delay in seconds between acquisition averages."""

    __state_file_dir: str = os.path.join(Path.home(), "nexus-console")
    """Storage location of the acquisition parameter state."""

    __save_on_mutation: bool = False
    """Flag which indicates if state is saved on mutation."""

    def __setattr__(self, __name: str, __value: Any) -> None:
        """Overwrite __setattr__ function to save object on each mutation.

        Requires __save_on_mutation flag which is set in __post_init__ method.
        """
        _hash = hash(self)
        super().__setattr__(__name, __value)
        if self.__save_on_mutation and hash(self) != _hash:
            print("Saving... ", self.__state_file_dir)
            self.save()

    def __post_init__(self) -> None:
        """Save state after initialization.

        Class is immutable, that means a new object is created for any update of the values.
        By calling the save method after initialization, updates are automatically saved as latest state.
        """
        self.__save_on_mutation = True

    def __repr__(self) -> str:
        """Representation of acquisition parameter as string."""
        return json.dumps(self.dict(), indent=4)

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
            return {k: str(v) for k, v in asdict(self).items() if not k.startswith("_")}
        return {k: v for k, v in asdict(self).items() if not k.startswith("_")}

    def save(self) -> None:
        """Save current acquisition parameter state.

        Parameters
        ----------
        file_path, optional
            Path to the pickle state file, by default "acquisition-parameter-state.pkl"
        """
        file_path = os.path.join(self.__state_file_dir, "acquisition-parameter.state")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as file:
            pickle.dump(self.__dict__, file)

    def hash(self) -> int:
        """Return acquisition parameter integer hash."""
        return self.__hash__()

    def directory(self) -> str:
        """Return directory of acquisition parameter state file."""
        return self.__state_file_dir

    @classmethod
    def load(cls, file_path: str) -> "AcquisitionParameter":
        """Load acquisition parameter state from state file in-place.

        Parameters
        ----------
        file_path, optional
            Path to acquisition parameter state file.
            If file_path is not a pickle file, i.e. ends with .pkl,
            the default state file designation acquisition-parameter.state is added.

        Returns
        -------
            Instance of acquisition parameters with state loaded from provided file_path.

        Raises
        ------
        FileNotFoundError
            Provided file_path is not a pickle file or does not exist.
        """
        if not file_path.endswith(".state"):
            file_path = os.path.join(file_path, "acquisition-parameter.state")
        if os.path.exists(file_path):
            with open(file_path, "rb") as state_file:
                state = pickle.load(state_file)  # noqa: S301

            return cls(**state)
        else:
            raise FileNotFoundError("Acquisition parameter state file not found: ", file_path)
