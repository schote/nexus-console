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

    dim_dict = {"x": x, "y": y, "z": z}
    dim = Dimensions.from_dict(dim_dict)

    assert x == dim.x
    assert y == dim.y
    assert z == dim.z
    assert dim.to_dict() == dim_dict


@pytest.mark.parametrize("generator", (get_random_int, get_random_float))
def test_dimensions_arithmetics(generator):
    """Test creations of dimensions object from dictionary."""
    dim = Dimensions(generator(), generator(), generator())

    dim *= 0
    assert dim.x == 0
    assert dim.y == 0
    assert dim.z == 0

    val_add = 2
    dim += val_add
    assert dim.x == val_add
    assert dim.y == val_add
    assert dim.z == val_add

    val_sub = 1
    dim -= val_sub
    assert dim.x == val_add - val_sub
    assert dim.y == val_add - val_sub
    assert dim.z == val_add - val_sub

