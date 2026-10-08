"""Spectrum-instrumentation card driver interface based on the spcm_core package.

Provides the driver functions of ``spcm_core`` together with all register and error constants.
If the spectrum driver is not installed, ``spcm_core`` raises on import. In this case the module
can still be imported (e.g. for tests, docs or systems without cards) and calling any driver
function raises a ``ConnectionError``.
"""

import ctypes
import logging
from typing import TYPE_CHECKING, Any

from console.spcm_control.spcm._constants import *

if TYPE_CHECKING:

    def __getattr__(name: str) -> Any:
        """Register and error constants are exported dynamically, see _constants."""
        raise AttributeError(name)


log = logging.getLogger("SPCM")

SPCM_DIR_PCTOCARD = 0
SPCM_DIR_CARDTOPC = 1

SPCM_BUF_DATA = 1000  # main data buffer for acquired or generated samples
SPCM_BUF_ABA = 2000  # buffer for ABA data, holds the A-DATA (slow samples)
SPCM_BUF_TIMESTAMP = 3000  # buffer for timestamps

# define pointer aliases (identical to the definitions in spcm_core)
int8 = ctypes.c_int8
int16 = ctypes.c_int16
int32 = ctypes.c_int32
int64 = ctypes.c_int64

ptr8 = ctypes.POINTER(int8)
ptr16 = ctypes.POINTER(int16)
ptr32 = ctypes.POINTER(int32)
ptr64 = ctypes.POINTER(int64)

uint8 = ctypes.c_uint8
uint16 = ctypes.c_uint16
uint32 = ctypes.c_uint32
uint64 = ctypes.c_uint64

uptr8 = ctypes.POINTER(uint8)
uptr16 = ctypes.POINTER(uint16)
uptr32 = ctypes.POINTER(uint32)
uptr64 = ctypes.POINTER(uint64)

try:
    from spcm_core import (
        spcm_dwDefTransfer_i64,
        spcm_dwGetContBuf_i64,
        spcm_dwGetErrorInfo_i32,
        spcm_dwGetParam_i32,
        spcm_dwGetParam_i64,
        spcm_dwInvalidateBuf,
        spcm_dwSetParam_i32,
        spcm_dwSetParam_i64,
        spcm_dwSetParam_i64m,
        spcm_hOpen,
        spcm_vClose,
    )

except Exception as e:  # spcm_core raises a generic Exception if the driver is missing or outdated
    # The exception variable is deleted when the except block ends, keep the message
    _driver_error = str(e)
    log.debug("SPCM driver not loaded: %s", _driver_error)

    def _driver_not_loaded(*args, **kwargs):
        raise ConnectionError(f"SPCM driver not loaded: {_driver_error}")

    spcm_hOpen = _driver_not_loaded
    spcm_vClose = _driver_not_loaded
    spcm_dwGetErrorInfo_i32 = _driver_not_loaded
    spcm_dwGetParam_i32 = _driver_not_loaded
    spcm_dwGetParam_i64 = _driver_not_loaded
    spcm_dwSetParam_i32 = _driver_not_loaded
    spcm_dwSetParam_i64 = _driver_not_loaded
    spcm_dwSetParam_i64m = _driver_not_loaded
    spcm_dwDefTransfer_i64 = _driver_not_loaded
    spcm_dwInvalidateBuf = _driver_not_loaded
    spcm_dwGetContBuf_i64 = _driver_not_loaded
