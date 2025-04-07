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

    def __mul__(self, other) -> "Dimensions":
        """Multiply dimension."""
        if isinstance(other, Dimensions):
            return Dimensions(x=self.x * other.x, y=self.y * other.y, z=self.z * other.z)
        else:
            return Dimensions(x=self.x * other, y=self.y * other, z=self.z * other)

    def __add__(self, other) -> "Dimensions":
        """Multiply dimension."""
        if isinstance(other, Dimensions):
            return Dimensions(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z)
        else:
            return Dimensions(x=self.x + other, y=self.y + other, z=self.z + other)

    def __sub__(self, other) -> "Dimensions":
        """Multiply dimension."""
        if isinstance(other, Dimensions):
            return Dimensions(x=self.x - other.x, y=self.y - other.y, z=self.z - other.z)
        else:
            return Dimensions(x=self.x - other, y=self.y - other, z=self.z - other)

    def __imul__(self, _):
        """In-place multiplication."""
        raise TypeError("In-place operations are not supported.\
            Use 'dimensions = dimensions * value' instead.")

    def __iadd__(self, _):
        """In-place addition."""
        raise TypeError("In-place operations are not supported.\
            Use 'dimensions = dimensions + value' instead.")

    def __isub__(self, _):
        """In-place addition."""
        raise TypeError("In-place operations are not supported.\
            Use 'dimensions = dimensions - value' instead.")
