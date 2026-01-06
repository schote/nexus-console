"""Test interfaces."""

import numpy as np
from copy import deepcopy
import pytest

from console.interfaces.dimensions import Dimensions

generator = np.random.default_rng()

def test_dimensions_from_dict():
    """Test creations of dimensions object from dictionary."""
    x, y, z = generator.random(3)
    dim_dict = {"x": x, "y": y, "z": z}
    dim = Dimensions.from_dict(dim_dict)

    assert x == dim.x
    assert y == dim.y
    assert z == dim.z
    assert dim.to_dict() == dim_dict


def test_dimensions_arithmetics():
    """Test creations of dimensions object from dictionary."""
    dim = Dimensions.from_list([float(x) for x in generator.random(3)])
    val = generator.random()

    dim_copy = deepcopy(dim)
    dim_copy *= val
    assert dim_copy == (dim * val)
    assert dim_copy != dim

    dim_copy = deepcopy(dim)
    dim_copy /= val
    assert dim_copy == (dim / val)
    assert dim_copy != dim

    dim_copy = deepcopy(dim)
    dim_copy += val
    assert dim_copy == (dim + val)
    assert dim_copy != dim

    dim_copy = deepcopy(dim)
    dim_copy -= val
    assert dim_copy == (dim - val)
    assert dim_copy != dim
