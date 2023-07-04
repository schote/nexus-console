from ctypes import *

# load registers for easier access
from console.spcm_control.py_header.regs import *


#
# **************************************************************************
# szTypeToName: doing name translation
# **************************************************************************
#
def szTypeToName(lCardType):
    sName = ""
    lVersion = lCardType & TYP_VERSIONMASK
    if (lCardType & TYP_SERIESMASK) == TYP_M2ISERIES:
        sName = "M2i.%04x" % lVersion
    elif (lCardType & TYP_SERIESMASK) == TYP_M2IEXPSERIES:
        sName = "M2i.%04x-Exp" % lVersion
    elif (lCardType & TYP_SERIESMASK) == TYP_M3ISERIES:
        sName = "M3i.%04x" % lVersion
    elif (lCardType & TYP_SERIESMASK) == TYP_M3IEXPSERIES:
        sName = "M3i.%04x-Exp" % lVersion
    elif (lCardType & TYP_SERIESMASK) == TYP_M4IEXPSERIES:
        sName = "M4i.%04x-x8" % lVersion
    elif (lCardType & TYP_SERIESMASK) == TYP_M4XEXPSERIES:
        sName = "M4x.%04x-x4" % lVersion
    elif (lCardType & TYP_SERIESMASK) == TYP_M2PEXPSERIES:
        sName = "M2p.%04x-x4" % lVersion
    elif (lCardType & TYP_SERIESMASK) == TYP_M5IEXPSERIES:
        sName = "M5i.%04x-x16" % lVersion
    else:
        sName = "unknown type"
    return sName


#
# **************************************************************************
# pvAllocMemPageAligned: creates a buffer for DMA that's page-aligned
# **************************************************************************
#
def pvAllocMemPageAligned(qwBytes):
    dwAlignment = 4096
    dwMask = dwAlignment - 1

    # allocate non-aligned, slightly larger buffer
    qwRequiredNonAlignedBytes = qwBytes * sizeof(c_char) + dwMask
    pvNonAlignedBuf = (c_char * qwRequiredNonAlignedBytes)()

    # get offset of next aligned address in non-aligned buffer
    misalignment = addressof(pvNonAlignedBuf) & dwMask
    if misalignment:
        dwOffset = dwAlignment - misalignment
    else:
        dwOffset = 0
    return (c_char * qwBytes).from_buffer(pvNonAlignedBuf, dwOffset)
