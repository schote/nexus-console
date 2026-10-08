"""Test spectrum-instrumentation registers."""
import re
from inspect import getmembers, isfunction
from pathlib import Path

import console.spcm_control.spcm._constants as reg
import console.spcm_control.spcm.pyspcm as sp

SPCM_CONTROL_DIR = Path(__file__).parents[2] / "src" / "console" / "spcm_control"


def test_reg_values():
    """Test all members of the spcm registers and error codes."""
    for module in [reg.regs, reg.spcerr]:
        for name, value in getmembers(module):
            if isfunction(value) or name.startswith("_"):
                continue
            assert isinstance(value, int)
            assert getattr(reg, name) == value


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


def test_used_symbols_available():
    """Check that every driver symbol used by the spectrum devices is provided by pyspcm."""
    pattern = re.compile(r"(?<![\w.])(?:sp|spcm)\.([A-Za-z_][A-Za-z0-9_]*)")
    used: set[str] = set()
    for file in ["abstract_device.py", "rx_device.py", "tx_device.py"]:
        used |= set(pattern.findall((SPCM_CONTROL_DIR / file).read_text(encoding="utf-8")))
    assert used
    missing = sorted(name for name in used if not hasattr(sp, name))
    assert not missing, f"Symbols missing in pyspcm: {missing}"
