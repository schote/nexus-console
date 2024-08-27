"""Interface class for acquisition parameters."""

import json
import os
import pickle  # noqa: S403
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from console.interfaces.dimensions import Dimensions
from console.interfaces.enums import DDCMethod

DEFAULT_STATE_FILE_PATH = os.path.join(Path.home(), "nexus-console", "acquisition-parameter.state")
DEFAULT_FOV_SCALING = Dimensions(x=1., y=1., z=1.)
DEFAULT_GRADIENT_OFFSET = Dimensions(x=0., y=0., z=0.)
FILENAME_STATE = "acquisition-parameter.state"


@dataclass(unsafe_hash=True)
class AcquisitionParameter:
    """
    Parameters to define an acquisition.

    The acquisition parameters are defined in a dataclass which is hashable but still mutable.
    This allows to easily change parameters and detect updates by comparing the hash.

    New instances of acquisition parameters are not saved automatically.
    Once the autosave flag is set by calling `activate_autosave`, the parameter state is
    written to a pickle file acquisition-parameter.state in the default_state_file_path on any
    mutation of the acquisition parameter instance.
    The autosave option can be deactivated calling `deactivate_autosave`.
    Manually storing the acquisition parameters to a specific directory can be achieved
    using the `save` method and providing the desired path.
    """

    larmor_frequency: float = 2.e6
    """Larmor frequency in MHz."""

    b1_scaling: float = 1.0
    """Scaling of the B1 field (RF transmit power)."""

    gradient_offset: Dimensions = DEFAULT_GRADIENT_OFFSET
    """Gradient offset values in mV."""

    fov_scaling: Dimensions = DEFAULT_FOV_SCALING
    """Field of view scaling for Gx, Gy and Gz."""

    decimation: int = 200
    """Decimation rate for initial down-sampling step."""

    ddc_method: DDCMethod = DDCMethod.FIR

    num_averages: int = 1
    """Number of acquisition averages."""

    averaging_delay: float = 0.0
    """Delay in seconds between acquisition averages."""

    default_state_file_path: str = DEFAULT_STATE_FILE_PATH
    """Default file path for acquisition parameter state."""

    save_on_mutation: bool = False
    """Flag which indicates if state is saved on mutation."""

    def __setattr__(self, __name: str, __value: Any) -> None:
        """Overwrite __setattr__ function to save object on each mutation.

        Requires __save_on_mutation flag which is set in __post_init__ method.
        """
        _hash = hash(self)
        super().__setattr__(__name, __value)
        if self.save_on_mutation and hash(self) != _hash:
            self.save()

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

    def save(self, file_path: str | None = None) -> None:
        """Save current acquisition parameter state.

        Parameters
        ----------
        file_path, optional
            Path to the pickle state file, by default None.
            If None, the default state file path is taken which is <home>/nexus-console/acquisition-parameter.state
            Default state file path can be changed using the set_default_path method.
        """
        if not file_path:
            file_path = self.default_state_file_path
        if not file_path.endswith(".state"):
            file_path = os.path.join(file_path, FILENAME_STATE)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        print("Saving acquisition parameter to: ", file_path)
        with open(file_path, "wb") as file:
            pickle.dump(self.__dict__, file)

    def hash(self) -> int:
        """Return acquisition parameter integer hash."""
        return self.__hash__()

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
            file_path = os.path.join(file_path, FILENAME_STATE)
        if os.path.exists(file_path):
            with open(file_path, "rb") as state_file:
                state = pickle.load(state_file)  # noqa: S301
            print("Loaded acquisition parameter state from file: ", file_path)
            print("Acquisition parameter:\n", state)
            return cls(**state)
        raise FileNotFoundError("Acquisition parameter state file not found: ", file_path)
