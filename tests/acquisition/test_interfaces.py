"""Test interfaces."""
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from console.interfaces.dimensions import Dimensions

generator = np.random.default_rng()


def get_random_int() -> int:
    """Return random integer value."""
    return generator.integers(low=0, high=10000)


def get_random_float() -> float:
    """Return random integer value."""
    return generator.random()


@pytest.mark.parametrize("generator", (get_random_int, get_random_float))
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
    assert dim.dict() == dim_dct


@pytest.mark.parametrize("generator", (get_random_int, get_random_float))
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
