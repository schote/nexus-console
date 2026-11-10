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
    """Runtime parameters of an acquisition.

    In contrast to the static device configuration, acquisition parameters describe the state of a
    measurement session (e.g. calibrated Larmor frequency and B1 scaling) and are passed to
    `AcquisitionControl.set_sequence` for each acquisition.

    The parameter state is persisted as JSON: it is written to `state_filepath` on instantiation and on
    every mutation of an attribute (including mutations of nested `Dimensions` attributes). Assignments are
    type-checked against the field annotations. On import of the `console` package, the last saved state is
    loaded and exposed as `console.parameter`.
    """

    larmor_frequency: float = 2.e6
    """Larmor frequency in Hz."""

    b1_scaling: float = 1.0
    """Scaling of the B1 field (RF transmit power)."""

    gradient_offset: Dimensions = field(default_factory=_gradient_offset_factory)
    """Static gradient offsets (e.g. for linear shimming) in mV.

    Given per physical output channel (x: channel 1, y: channel 2, z: channel 3) and applied as hardware
    DC offset of the transmit card for the duration of an acquisition.
    """

    fov_scaling: Dimensions = field(default_factory=_fov_scaling_factory)
    """Scaling factor of the logical gradient waveforms gx, gy and gz."""

    channel_assignment: Dimensions = field(default_factory=_channel_factory)
    """Assignment of the logical gradients x, y, z to the physical transmit channels 1, 2, 3.

    Must be a permutation of {1, 2, 3}.
    """

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

    def __setattr__(self, name: str, value: object) -> None:
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

    def __eq__(self, other: object) -> bool:
        """Compare acquisition parameter to other instance."""
        if not isinstance(other, AcquisitionParameter):
            return NotImplemented
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
        use_strings
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
        filepath : str or Path or None, optional
            Path to the JSON state file. If None, `state_filepath` is used
            (default ``<home>/nexus-console/acquisition-parameter.state``).
            If the path does not end with ``.state``, it is interpreted as directory and the
            filename ``acquisition-parameter.state`` is appended.
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
        filepath : Path or str or None, optional
            Path to acquisition parameter state file. If the path does not end with
            ``.state``, the filename ``acquisition-parameter.state`` is appended.

        Returns
        -------
        AcquisitionParameter or None
            Instance of acquisition parameters with state loaded from the provided path, or None if the
            state file does not exist or cannot be parsed (the error is logged).
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
