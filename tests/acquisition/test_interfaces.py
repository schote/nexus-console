"""Test interfaces."""
import pytest

from console.interfaces.dimensions import Dimensions
from console.interfaces.enums import DDCMethod
import numpy as np
from dataclasses import FrozenInstanceError


@pytest.mark.parametrize(
    "generator", (lambda: np.random.randint(low=0, high=10000), lambda: np.random.random())
)
def test_dimensions_from_dict(generator):
    """Test creations of dimensions object from dictionary."""
    x = generator()
    y = generator()
    z = generator()

    dim_dct = {"x": x, "y": y, "z": z}
    dim = Dimensions.from_dict(dim_dct)

    assert x == dim.x
    assert y == dim.y
    assert z == dim.z
    assert dim.as_dict() == dim_dct


@pytest.mark.parametrize(
    "generator", (lambda: np.random.randint(low=0, high=10000), lambda: np.random.random())
)
def test_dimensions(generator):
    """Test creations of dimensions object and check if instance is frozen."""
    x = generator()
    y = generator()
    z = generator()

    dim = Dimensions(x=x, y=y, z=z)

    assert x == dim.x
    assert y == dim.y
    assert z == dim.z

    with pytest.raises(FrozenInstanceError):
        dim.x = generator()
        dim.y = generator()
        dim.z = generator()

    print("test done.")
