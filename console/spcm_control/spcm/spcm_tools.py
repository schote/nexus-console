"""Tools for spectrum card."""

from ctypes import *
from typing import Any

# load registers for easier access
import console.spcm_control.py_header.regs as regs
from console.spcm_control.py_header.errors import error_reg
from console.spcm_control.py_header.status import status_reg, status_reg_desc


def translate_status(status: int, include_desc: bool = False) -> tuple[dict[int, list[Any]], list[str]]:
    """Translate integer value to readable status message.

    Parameters
    ----------
    status
        Status code from spectrum card device

    Returns
    -------
        Description from user manual, default is unknown
    """
    # Convert status code to 12-digit bit sequence in reversed order
    # >> lowest bit comes first => correspondence to order in manual
    bit_reg = list(reversed("{:012b}".format(status)))

    # Status codes are defined for card (0x1 ... 0x8) and data (0x100 ... 0x800)
    # >> First 4 bits correspond to (0x1 ... 0x8)
    # >> Last 4 bits correspond to (0x100 ... 0x800)
    status_flags_card = [bool(int(b)) for b in bit_reg[:4]]
    status_flags_data = [bool(int(b)) for b in bit_reg[-4:]]
    status_flags = status_flags_card + status_flags_data

    # Construct status dictionary, include description depending on function argument
    status_dict: dict[int, list] = {}
    for k, (val, stat) in enumerate(status_reg.items()):
        status_dict[val] = [status_flags[k], stat, status_reg_desc[val]] if include_desc else [status_flags[k], stat]

    return status_dict, bit_reg


def translate_error(error: int) -> str:
    """Translate error code to description string from manual.

    Parameters
    ----------
    error
        Error code to be translated

    Returns
    -------
        Error description string from user manual
    """
    if error in error_reg.keys():
        return "ERROR: {}".format(error_reg[error])
    else:
        return "Unknown error."


def type_to_name(card_type: int) -> str:
    """Name translation for card type.

    Parameters
    ----------
    lCardType
        Card code

    Returns
    -------
        Card name as string
    """
    version = card_type & regs.TYP_VERSIONMASK
    code = card_type & regs.TYP_SERIESMASK
    match code:
        case regs.TYP_M2ISERIES:
            return "M2i.%04x" % version
        case regs.TYP_M2IEXPSERIES:
            return "M2i.%04x-Exp" % version
        case regs.TYP_M3ISERIES:
            return "M3i.%04x" % version
        case regs.TYP_M3IEXPSERIES:
            return "M3i.%04x-Exp" % version
        case regs.TYP_M4IEXPSERIES:
            return "M4i.%04x-x8" % version
        case regs.TYP_M4XEXPSERIES:
            return "M4x.%04x-x4" % version
        case regs.TYP_M2PEXPSERIES:
            return "M2p.%04x-x4" % version
        case regs.TYP_M5IEXPSERIES:
            return "M5i.%04x-x16" % version
        case _:
            return "unknown type"


def create_dma_buffer(buffer_size: int):
    """Allocate memory for page-aligned DMA buffer.

    Parameters
    ----------
    buffer_size
        Size of the buffer

    Returns
    -------
        Buffer
    """
    dwAlignment = 4096
    dwMask = dwAlignment - 1

    # allocate non-aligned, slightly larger buffer
    qwRequiredNonAlignedBytes = buffer_size * sizeof(c_char) + dwMask
    pvNonAlignedBuf = (c_char * qwRequiredNonAlignedBytes)()

    # get offset of next aligned address in non-aligned buffer
    misalignment = addressof(pvNonAlignedBuf) & dwMask
    if misalignment:
        dwOffset = dwAlignment - misalignment
    else:
        dwOffset = 0
    return (c_char * buffer_size).from_buffer(pvNonAlignedBuf, dwOffset)
