"""Test loading of the spectrum-instrumentation driver interface."""
import pytest

import console.spcm_control.spcm.pyspcm as sp


def test_driver_not_loaded():
    """Without a driver, pyspcm must be importable and driver calls raise a connection error."""
    if sp.spcm_hOpen.__name__ != "_driver_not_loaded":
        pytest.skip("Spectrum driver is installed.")
    with pytest.raises(ConnectionError):
        sp.spcm_hOpen(b"/dev/spcm0")


def test_ctypes_aliases():
    """Check ctypes aliases used for card communication."""
    assert sp.int32(5).value == 5
    assert sp.uint64(2**40).value == 2**40
    assert sp.SPCM_DIR_CARDTOPC == 1
    assert sp.SPCM_DIR_PCTOCARD == 0
    assert sp.SPCM_BUF_DATA == 1000
    assert sp.SPCM_BUF_TIMESTAMP == 3000
