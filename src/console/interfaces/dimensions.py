"""Interface class for dimensions."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from typing_extensions import Self


def _dict_factory(items: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    """Return a dictionary containing only fields whose names do not start with '_'."""
    return {key: value for key, value in items if not key.startswith("_")}


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
        """Convert to a dictionary."""
        return asdict(self, dict_factory=_dict_factory)

    @classmethod
    def from_list(cls, dim: list[int | float]) -> Dimensions:
        """Create a Dimensions instance from a list."""
        return cls(*dim)

    def to_list(self) -> list[int | float]:
        """Convert to a list."""
        return [self.x, self.y, self.z]

    def __setattr__(self, name: str, value: float) -> None:
        """Overwrite setter to trigger private on_change method if set."""
        if name in ("x", "y", "z") and not isinstance(value, (int, float)):
            msg = f"Invalid value: {value}, only (int, float) is allowed."
            raise TypeError(msg)
        super().__setattr__(name, value)
        if not hasattr(self, "_on_change"):
            return
        if name in ("x", "y", "z") and callable(self._on_change):
            # Trigger on_change callback to trigger parent save
            self._on_change()

    def __format__(self, format_spec: str = "") -> str:
        """Return formatted string with applied format spec to all values."""
        if format_spec:
            return f"x={self.x:{format_spec}}, y={self.y:{format_spec}}, z={self.z:{format_spec}}"
        return f"x={self.x}, y={self.y}, z={self.z}"

    # ---------------- Arithmetic ---------------- #
    # Note: The arguments do not have an int typ annotation, since float also allows ints.
    # See https://docs.astral.sh/ruff/rules/redundant-numeric-union/

    def __mul__(self, other: float | Dimensions) -> Dimensions:
        """Multiply dimension."""
        if isinstance(other, Dimensions):
            return Dimensions(x=self.x * other.x, y=self.y * other.y, z=self.z * other.z)
        return Dimensions(x=self.x * other, y=self.y * other, z=self.z * other)

    def __truediv__(self, other: float | Dimensions) -> Dimensions:
        """Divide dimension."""
        if isinstance(other, Dimensions):
            return Dimensions(x=self.x / other.x, y=self.y / other.y, z=self.z / other.z)
        return Dimensions(x=self.x / other, y=self.y / other, z=self.z / other)

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

    def __itruediv__(self, other: float | Dimensions) -> Self:
        """In-place division."""
        if isinstance(other, Dimensions):
            self.x /= other.x
            self.y /= other.y
            self.z /= other.z
        else:
            self.x /= other
            self.y /= other
            self.z /= other
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
