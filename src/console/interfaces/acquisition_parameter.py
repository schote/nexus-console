"""Interface class for acquisition parameters."""
import json
import logging
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from console.interfaces.dimensions import Dimensions
from console.interfaces.enums import DDCMethod


def _gradient_offset_factory() -> Dimensions:
    return Dimensions(x=0, y=0, z=0)


def _fov_scaling_factory() -> Dimensions:
    return Dimensions(x=1., y=1., z=1.)


def _channel_factory() -> Dimensions:
    return Dimensions(x=1, y=2, z=3)


def _dict_factory(items: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    """Return a dictionary containing only fields whose names do not start with '_'."""
    return {key: value for key, value in items if not key.startswith("_")}


@dataclass
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
    """Larmor frequency in Hz."""

    b1_scaling: float = 1.0
    """Scaling of the B1 field (RF transmit power)."""

    gradient_offset: Dimensions = field(default_factory=_gradient_offset_factory)
    """Gradient offset values in mV."""

    fov_scaling: Dimensions = field(default_factory=_fov_scaling_factory)
    """Field of view scaling for Gx, Gy and Gz."""

    channel_assignment: Dimensions = field(default_factory=_channel_factory)
    """Assignment of console output channels to gradient channels x, y, z."""

    ddc_method: DDCMethod = DDCMethod.FIR
    """Decimation filter method."""

    num_averages: int = 1
    """Number of acquisition averages."""

    averaging_delay: float = 0.0
    """Delay in seconds between acquisition averages."""

    state_filepath: str = str(Path.home() / "nexus-console/acquisition-parameter.state")
    """Default file path for acquisition parameter state.

    Don't enforce a Path object here to prevent conflicts when sending acquisition parameter
    instances between different OS.
    """

    _initialized: bool = field(default=False, init=True, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        """Post initialization method."""
        # Ensure Dimensions type
        if isinstance(self.gradient_offset, dict):
            self.gradient_offset = Dimensions.from_dict(self.gradient_offset)
        if isinstance(self.fov_scaling, dict):
            self.fov_scaling = Dimensions.from_dict(self.fov_scaling)
        if isinstance(self.channel_assignment, dict):
            self.channel_assignment = Dimensions.from_dict(self.channel_assignment)

        # Register child change callback to trigger a save when child changed
        self.gradient_offset.register_on_change_callback(self._child_changed)
        self.fov_scaling.register_on_change_callback(self._child_changed)
        self.channel_assignment.register_on_change_callback(self._child_changed)

        _path = Path(self.state_filepath)
        if not _path.name.endswith(".state"):
            _path = _path / "acquisition-parameter.state"
        # Ensure state filepath is a string
        self.state_filepath = str(_path)

        self._initialized = True
        self.save()

    def __setattr__(self, name: str, value: Any) -> None:
        """Overwrite __setattr__ function to save object on each mutation."""
        # Get type hints for the class
        hints = self.__class__.__annotations__
        if self._initialized:
            # Skip validation for private attributes
            if not name.startswith("_") and name in hints:
                expected_type = hints[name]
                if not isinstance(value, expected_type):
                    # Raise error on type mismatch
                    msg = f"Attribute '{name}' must be of type {expected_type.__name__}, got {type(value).__name__}"
                    raise TypeError(msg)
            prev = self.to_dict()
            super().__setattr__(name, value)
            if self.to_dict() != prev:
                self.save()
        else:
            super().__setattr__(name, value)

    def __eq__(self, other) -> bool:
        """Compare acquisition parameter to other instance."""
        if not isinstance(other, AcquisitionParameter):
            return False
        # deep dict comparison, including nested dataclasses
        return self.to_dict() == other.to_dict()

    def __str__(self) -> str:
        """Get string representation of acquisition parameter."""
        data = self.to_dict()
        output = "Acquisition parameter\n----------\n"
        for k, (key, value) in enumerate(data.items()):
            output += f"{key} = {value}" if k == len(data) - 1 else f"{key} = {value}\n"
        return output

    def __copy__(self) -> "AcquisitionParameter":
        """Copy acquisition parameter."""
        cls = self.__class__
        result = cls(**self.__dict__)
        result._initialized = True
        return result

    def _child_changed(self) -> None:
        """Save acquisition parameters if child changed."""
        if self._initialized:
            self.save()

    def to_dict(self, use_strings: bool = False) -> dict:
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
            return {key: str(value) for key, value in asdict(self, dict_factory=_dict_factory).items()}
        return asdict(self, dict_factory=_dict_factory)

    def save(self, filepath: str | Path | None = None) -> None:
        """Save current acquisition parameter state.

        Parameters
        ----------
        file_path, optional
            Path to the pickle state file, by default None.
            If None, the default state file path is taken which is <home>/nexus-console/acquisition-parameter.state
            Default state file path can be changed using the set_default_path method.
        """
        _path = Path(filepath or self.state_filepath)
        if not _path.name.endswith(".state"):
            _path = _path / "acquisition-parameter.state"
        _path.parent.mkdir(parents=True, exist_ok=True)
        _path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, filepath: Path | str | None = None) -> Optional["AcquisitionParameter"]:
        """
        Load and return acquisition parameter state.

        Parameters
        ----------
        file_path, optional
            Path to acquisition parameter state file.
            If file_path is not a pickle file, i.e. ends with .json,
            the default state file designation acquisition-parameter.state is added.

        Returns
        -------
            Instance of acquisition parameters with state loaded from provided file_path.

        Raises
        ------
        FileNotFoundError
            Provided file_path is not a pickle file or does not exist.
        EOFError
            Provided state file is corrupted
        """
        log = logging.getLogger("AcqParam")

        # Resolve file path
        _path = filepath or cls.state_filepath
        _path = Path(_path)

        # Enforce `.state` suffix
        if not _path.name.endswith(".state"):
            _path = _path / "acquisition-parameter.state"

        try:
            data = json.loads(_path.read_text())
            return cls(**data)
        except Exception:
            log.exception(
                "Error loading AcquisitionParameter state file '%s'.",
                str(_path),
            )
            return None
