"""Interface class for dimensions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dimensions:
    """Dataclass for definition of dimensional parameters."""

    x: float | int  # pylint: disable=invalid-name
    """X dimension."""

    y: float | int  # pylint: disable=invalid-name
    """Y dimension."""

    z: float | int  # pylint: disable=invalid-name
    """Z dimension."""

    @classmethod
    def from_dict(cls, dim: dict[str, float | int]) -> "Dimensions":
        """Create a dimensions instance from dictionary."""
        return cls(x=dim["x"], y=dim["y"], z=dim["z"])

    def dict(self) -> dict[str, float | int]:
        """Create dictionary of dimensions object."""
        return {"x": self.x, "y": self.y, "z": self.z}

    def __str__(self):
        """Return custom representation string."""
        return f"x={self.x}, y={self.y}, z={self.z}"
