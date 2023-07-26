from ctypes import *

# load registers for easier access
import console.spcm_control.py_header.regs as regs
from console.spcm_control.py_header.spcerr import error_translation


def translate_status(status: int) -> str:
    """Translate integer value to readable status message.

    Parameters
    ----------
    status
        Status code from spectrum card device

    Returns
    -------
        Description from user manual, default is unknown
    """
    match status:
        case 0x100: 
            return "The next data block as defined in the notify size is available. It is at least the amount of data available but it also can be more data."
        case 0x200: 
            return "The data transfer has completed. This status information will only occur if the notify size is set to zero."
        case 0x400:
            return "The data transfer had on overrun (acquisition) or underrun (replay) while doing FIFO transfer."
        case 0x800: 
            return "An internal error occurred while doing data transfer."
        case _:
            if status in error_translation.keys():
                return "ERROR: {}".format(error_translation[status])
            else:
                return "Unknown status."


def translate_error(error: int) -> str:
    if error in error_translation.keys():
        return "ERROR: {}".format(error_translation[error])
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
