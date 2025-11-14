"""Interface class for dimensions."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from typing_extensions import Self


@dataclass
class Dimensions:
    """Dataclass for definition of dimensional parameters."""

    x: int | float  # pylint: disable=invalid-name
    """X dimension."""

    y: int | float  # pylint: disable=invalid-name
    """Y dimension."""

    z: int | float  # pylint: disable=invalid-name
    """Z dimension."""

    _on_change: Callable | None = field(default=None, init=False, repr=False, compare=False)

    def register_on_change_callback(self, callback: Callable) -> None:
        """Register on change callback to protected attribute."""
        if callable(callback):
            self._on_change = callback

    @classmethod
    def from_dict(cls, dim: dict[str, int | float]) -> Dimensions:
        """Create a Dimensions instance from a dictionary."""
        required = ("x", "y", "z")

        # Ensure all required keys exist
        if missing := [key for key in required if key not in dim]:
            msg = f"Missing keys for Dimensions: {missing}"
            raise ValueError(msg)

        # Extract only the keys relevant for initialization
        return cls(**{key: dim[key] for key in required})

    def to_dict(self) -> dict[str, int | float]:
        """Convert to a nested dictionary."""
        return asdict(self)

    def __setattr__(self, name: str, value: float) -> None:
        """Overwrite setter to trigger private on_change method if set."""
        super().__setattr__(name, value)
        if not hasattr(self, "_on_change"):
            return
        if name in ("x", "y", "z") and callable(self._on_change):
            # Trigger on_change callback to trigger parent save
            self._on_change()

    def __str__(self) -> str:
        """Return custom representation string."""
        return f"x={self.x}, y={self.y}, z={self.z}"

    # ---------------- Arithmetic ---------------- #
    # Note: The arguments do not have an int typ annotation, since float also allows ints.
    # See https://docs.astral.sh/ruff/rules/redundant-numeric-union/

    def __mul__(self, other: float | Dimensions) -> Dimensions:
        """Multiply dimension."""
        if isinstance(other, Dimensions):
            return Dimensions(x=self.x * other.x, y=self.y * other.y, z=self.z * other.z)
        return Dimensions(x=self.x * other, y=self.y * other, z=self.z * other)

    def __add__(self, other: float | Dimensions) -> Dimensions:
        """Add dimension."""
        if isinstance(other, Dimensions):
            return Dimensions(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z)
        return Dimensions(x=self.x + other, y=self.y + other, z=self.z + other)

    def __sub__(self, other: float | Dimensions) -> Dimensions:
        """Subtract dimension."""
        if isinstance(other, Dimensions):
            return Dimensions(x=self.x - other.x, y=self.y - other.y, z=self.z - other.z)
        return Dimensions(x=self.x - other, y=self.y - other, z=self.z - other)

    def __imul__(self, other: float | Dimensions) -> Self:
        """In-place multiplication."""
        if isinstance(other, Dimensions):
            self.x *= other.x
            self.y *= other.y
            self.z *= other.z
        else:
            self.x *= other
            self.y *= other
            self.z *= other
        return self

    def __iadd__(self, other: float | Dimensions) -> Self:
        """In-place addition."""
        if isinstance(other, Dimensions):
            self.x += other.x
            self.y += other.y
            self.z += other.z
        else:
            self.x += other
            self.y += other
            self.z += other
        return self

    def __isub__(self, other: float | Dimensions) -> Self:
        """In-place subtraction."""
        if isinstance(other, Dimensions):
            self.x -= other.x
            self.y -= other.y
            self.z -= other.z
        else:
            self.x -= other
            self.y -= other
            self.z -= other
        return self
