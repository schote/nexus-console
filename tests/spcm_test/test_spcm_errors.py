"""Check spcm error codes and description."""
from inspect import getmembers

import console.spcm_control.spcm.errors as err


def test_error_description():
    """Test content of spcm error register description."""
    for key, value in err.error_reg.items():
        assert isinstance(key, int)
        assert isinstance(value, str)


def test_error_values():
    """Check if all error values are integers."""
    for var in getmembers(err):
        if var[0].startswith(("ERR", "SPCM")):
            assert isinstance(var[1], int)
