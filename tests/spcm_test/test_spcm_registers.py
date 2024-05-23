"""Test spectrum-instrumentation registers."""
from inspect import getmembers, isfunction

import console.spcm_control.spcm.registers as reg


def test_reg_values():
    """Test all members of the spcm registers."""
    for var in getmembers(reg):
        if isfunction(var[1]) or var[0].startswith(("__", "_")):
            continue
        assert isinstance(var[1], int)


def test_conversions():
    """Test value conversions."""
    assert reg.KILO(1) == 1000
    assert reg.MEGA(1) == 1000 ** 2
    assert reg.GIGA(1) == 1000 ** 3


def test_byte_conversions():
    """Test byte-value conversions."""
    assert reg.KILO_B(1) == 1024
    assert reg.MEGA_B(1) == 1024 ** 2
    assert reg.GIGA_B(1) == 1024 ** 3
