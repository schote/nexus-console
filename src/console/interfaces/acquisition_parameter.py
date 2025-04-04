"""Interface class for acquisition parameters."""

import pickle  # noqa: S403
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from console.interfaces.dimensions import Dimensions
from console.interfaces.enums import DDCMethod


def _grad_factory() -> Dimensions:
    return Dimensions(x=0., y=0., z=0.)

def _fov_factory() -> Dimensions:
    return Dimensions(x=1., y=1., z=1.)

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

    gradient_offset: Dimensions = field(default_factory=_grad_factory)
    """Gradient offset values in mV."""

    fov_scaling: Dimensions = field(default_factory=_fov_factory)
    """Field of view scaling for Gx, Gy and Gz."""

    decimation: int = 200
    """Decimation rate for initial down-sampling step."""

    ddc_method: DDCMethod = DDCMethod.FIR

    num_averages: int = 1
    """Number of acquisition averages."""

    averaging_delay: float = 0.0
    """Delay in seconds between acquisition averages."""

    state_filepath: Path = Path.home() / Path("nexus-console/acquisition-parameter.state")
    """Default file path for acquisition parameter state."""

    _initialized: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        """Post initialization method."""
        if not self.state_filepath.name.endswith(".state"):
            self.state_filepath = self.state_filepath / "acquisition-parameter.state"
        self._initialized = True
        self.save()

    def __setattr__(self, name: str, value: Any) -> None:
        """Overwrite __setattr__ function to save object on each mutation."""
        if self._initialized:
            _hash = hash(self)
            super().__setattr__(name, value)
            if hash(self) != _hash:
                print("Saving parameter...")
                self.save()
        else:
            super().__setattr__(name, value)

    def __str__(self):
        """Get string representation of acquisition parameter."""
        data = self.dict()
        output = "Acquisition parameter\n----------\n"
        for k, (key, value) in enumerate(data.items()):
            output += f"{key} = {value}" if k == len(data)-1 else f"{key} = {value}\n"
        return output

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

    def save(self, filepath: str | Path | None = None) -> None:
        """Save current acquisition parameter state.

        Parameters
        ----------
        file_path, optional
            Path to the pickle state file, by default None.
            If None, the default state file path is taken which is <home>/nexus-console/acquisition-parameter.state
            Default state file path can be changed using the set_default_path method.
        """
        _filepath = filepath if filepath else self.state_filepath
        if isinstance(_filepath, str):
            _filepath = Path(_filepath)
        if not _filepath.name.endswith(".state"):
            _filepath = _filepath / "acquisition-parameter.state"
        _filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(_filepath, "wb") as file:
            pickle.dump(self.__dict__, file)

    def hash(self) -> int:
        """Return acquisition parameter integer hash."""
        return self.__hash__()

    @classmethod
    def load(cls, filepath: Path) -> "AcquisitionParameter":
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
        if not filepath.exists():
            raise FileNotFoundError("Acquisition parameter state file not found: ", filepath)
        with open(filepath, "rb") as state_file:
            state = pickle.load(state_file)  # noqa: S301
        return cls(**state)
