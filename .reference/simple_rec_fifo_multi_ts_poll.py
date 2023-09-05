#
# **************************************************************************
#
# simple_rec_fifo_multi_ts_poll.py                         (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for all SpcmDrv digital acquisition cards. 
# Shows a simple standard mode example using only the few necessary commands
#
# Information about the different products and their drivers can be found
# online in the Knowledge Base:
# https://www.spectrum-instrumentation.com/en/platform-driver-and-series-differences
#
# Feel free to use this source for own projects and modify it in any way
#
# Documentation for the API as well as a detailed description of the hardware
# can be found in the manual for each device which can be found on our website:
# https://www.spectrum-instrumentation.com/en/downloads
#
# Further information can be found online in the Knowledge Base:
# https://www.spectrum-instrumentation.com/en/knowledge-base-overview
#
# **************************************************************************
#

import sys

# import spectrum driver functions
from pyspcm import *
from spcm_tools import *

from console.spcm_control.device_interface import SpectrumDevice
from console.spcm_control.spcm.pyspcm import *  # noqa # pylint: disable=wildcard-import,unused-wildcard-import
from console.spcm_control.spcm.spcm_tools import create_dma_buffer, translate_status
#
# **************************************************************************
# main
# **************************************************************************
#

szErrorTextBuffer = create_string_buffer (ERRORTEXTLEN)
dwError = uint32 ()
lStatus = int32 ()
lAvailUser = int32 ()
lPCPos = int32 ()
lAvailUserTS = int32 ()
lPCPosTS = int32 ()
lChCount = int32 ()
qwTotalMem = uint64 (0)
qwToTransfer = uint64 (MEGA_B(8))
lSegmentIndex = uint32 (0)
lSegmentCnt = uint32 (0)
llSamplingrate = int64 (0)

# settings for the FIFO mode buffer handling
qwBufferSize = uint64 (MEGA_B(4))
lNotifySize = int32 (KILO_B(8))

qwBufferSizeTS = uint64 (MEGA_B(1))
lNotifySizeTS = int32 (KILO_B(4))

# open card
# uncomment the second line and replace the IP address to use remote
# cards like in a digitizerNETBOX
hCard = spcm_hOpen (create_string_buffer (b'/dev/spcm0'))
#hCard = spcm_hOpen (create_string_buffer (b'TCPIP::192.168.1.10::inst0::INSTR'))
if hCard == None:
    sys.stdout.write("no card found...\n")
    exit (1)

# read type, function and sn and check for A/D card
lCardType = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_PCITYP, byref (lCardType))
lSerialNumber = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_PCISERIALNO, byref (lSerialNumber))
lFncType = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_FNCTYPE, byref (lFncType))
lFeatureMap = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_PCIFEATURES, byref (lFeatureMap))

sCardName = szTypeToName (lCardType.value)
if lFncType.value == SPCM_TYPE_AI:
    sys.stdout.write("Found: {0} sn {1:05d}\n".format(sCardName,lSerialNumber.value))
else:
    sys.stdout.write("This is an example for A/D cards.\nCard: {0} sn {1:05d} not supported by example\n".format(sCardName,lSerialNumber.value))
    spcm_vClose (hCard)
    exit (1) 

if (lFeatureMap.value & SPCM_FEAT_MULTI == 0):
    sys.stdout.write ("Multiple Recording Option not installed !\n")
    spcm_vClose (hCard)
    exit (1)

if (lFeatureMap.value & SPCM_FEAT_TIMESTAMP == 0):
    sys.stdout.write ("Timestamp Option not installed !\n")
    spcm_vClose (hCard)
    exit (1)

lSegmentSize = 4096

# do a simple standard setup
spcm_dwSetParam_i32 (hCard, SPC_CHENABLE,         1)                      # just 1 channel enabled
spcm_dwSetParam_i32 (hCard, SPC_PRETRIGGER,       1024)                   # 1k of pretrigger data at start of FIFO mode
spcm_dwSetParam_i32 (hCard, SPC_CARDMODE,         SPC_REC_FIFO_MULTI)     # multiple recording FIFO mode
spcm_dwSetParam_i32 (hCard, SPC_SEGMENTSIZE,      lSegmentSize)           # set segment size
spcm_dwSetParam_i32 (hCard, SPC_POSTTRIGGER,      lSegmentSize - 128)     # set posttrigger
spcm_dwSetParam_i32 (hCard, SPC_LOOPS,            0)                      # set loops
spcm_dwSetParam_i32 (hCard, SPC_CLOCKMODE,        SPC_CM_INTPLL)          # clock mode internal PLL
spcm_dwSetParam_i32 (hCard, SPC_CLOCKOUT,         0)                      # no clock output
spcm_dwSetParam_i32 (hCard, SPC_TRIG_EXT0_MODE,   SPC_TM_POS)             # set trigger mode
spcm_dwSetParam_i32 (hCard, SPC_TRIG_TERM,        0)                      # set trigger termination
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,      SPC_TMASK_EXT0)         # trigger set to external
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ANDMASK,     0)                      # ...
spcm_dwSetParam_i32 (hCard, SPC_TRIG_EXT0_ACDC,   COUPLING_DC);           # trigger coupling
spcm_dwSetParam_i32 (hCard, SPC_TRIG_EXT0_LEVEL0, 1500);                  # trigger level of 1.5 Volt
spcm_dwSetParam_i32 (hCard, SPC_TRIG_EXT0_LEVEL1, 0);                     # unused
spcm_dwSetParam_i32 (hCard, SPC_TIMEOUT,          5000)                   # timeout 5 s

spcm_dwGetParam_i32 (hCard, SPC_CHCOUNT, byref (lChCount))
for lChannel in range (0, lChCount.value, 1):
    spcm_dwSetParam_i32 (hCard, SPC_AMP0 + lChannel * (SPC_AMP1 - SPC_AMP0), 1000)

# we try to set the samplerate to 100 kHz (M2i) or 20 MHz on internal PLL, no clock output
if ((lCardType.value & TYP_SERIESMASK) == TYP_M2ISERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M2IEXPSERIES):
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, int64 (KILO(100)))
else:
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, int64 (MEGA(20)))

# 1 timestamp = 8 bytes (M2i, M3i) or 16 bytes (M4i, M4x, M2p, M5i)
lBytesPerTS = 8
if ((lCardType.value & TYP_SERIESMASK) == TYP_M4IEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M4XEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M2PEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M5IEXPSERIES):
    lBytesPerTS = 16

# read back current sampling rate from driver
spcm_dwGetParam_i64 (hCard, SPC_SAMPLERATE, byref (llSamplingrate))

# setup timestamps
spcm_dwSetParam_i32 (hCard, SPC_TIMESTAMP_CMD, SPC_TSMODE_STARTRESET | SPC_TSCNT_INTERNAL)

# open file to save timestamps
fileTS = open ('timestamps.txt', 'w')

# define the data buffer
# we try to use continuous memory if available and big enough
pvBuffer = ptr8() # will be cast to correct type later
qwContBufLen = uint64 (0)
spcm_dwGetContBuf_i64 (hCard, SPCM_BUF_DATA, byref(pvBuffer), byref(qwContBufLen))
sys.stdout.write ("ContBuf length: {0:d}\n".format(qwContBufLen.value))
if qwContBufLen.value >= qwBufferSize.value:
    sys.stdout.write("Using continuous buffer\n")
else:
    pvBuffer = cast (pvAllocMemPageAligned (qwBufferSize.value), ptr8) # cast to ptr8 to make it behave like the continuous memory
    sys.stdout.write("Using buffer allocated by user program\n")

sys.stdout.write ("\n  !!! Using external trigger - please connect a signal to the trigger input !!!\n\n")

# setup buffer for data transfer
spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, lNotifySize, pvBuffer, uint64 (0), qwBufferSize)

# define the timestamps buffer
pvBufferTS = c_void_p ()
pvBufferTS = create_string_buffer (qwBufferSizeTS.value)

# setup buffer for timestamps transfer
spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_TIMESTAMP, SPCM_DIR_CARDTOPC, lNotifySizeTS, pvBufferTS, uint64 (0), qwBufferSizeTS)

pllData = cast (pvBufferTS, ptr64) # cast to pointer to 64bit integer

# activate polling mode for timestamp transfer
spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_EXTRA_POLL)

# start everything
dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER | M2CMD_DATA_STARTDMA)

# check for error
if dwError != 0: # != ERR_OK
    spcm_dwGetErrorInfo_i32 (hCard, None, None, szErrorTextBuffer)
    sys.stdout.write("{0}\n".format(szErrorTextBuffer.value))
    spcm_vClose (hCard)
    exit (1)

# run the FIFO mode and loop through the data
else:
    lMin = int (32767)  # normal python type
    lMax = int (-32768) # normal python type
    while qwTotalMem.value < qwToTransfer.value:
        dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_DATA_WAITDMA)
        if dwError != ERR_OK:
            if dwError == ERR_TIMEOUT:
                sys.stdout.write ("... Timeout\n")
            else:
                sys.stdout.write ("... Error: {0:d}\n".format(dwError))
                break;

        else:
            spcm_dwGetParam_i32 (hCard, SPC_M2STATUS,            byref (lStatus))
            spcm_dwGetParam_i32 (hCard, SPC_DATA_AVAIL_USER_LEN, byref (lAvailUser))
            spcm_dwGetParam_i32 (hCard, SPC_DATA_AVAIL_USER_POS, byref (lPCPos))

            if lAvailUser.value >= lNotifySize.value:
                qwTotalMem.value += lNotifySize.value

                # this is the point to do anything with the data
                # e.g. calculate minimum and maximum of the acquired data
                pnData = cast  (addressof (pvBuffer.contents) + lPCPos.value, ptr16) # cast to pointer to 16bit integer
                lNumSamples = int (lNotifySize.value / 2) # two bytes per sample
                for i in range (0, lNumSamples - 1, 1):
                    if pnData[i] < lMin:
                        lMin = pnData[i]
                    if pnData[i] > lMax:
                        lMax = pnData[i]

                    lSegmentIndex.value += 1
                    lSegmentIndex.value %= lSegmentSize

                    # check end of acquired segment
                    if (lSegmentIndex.value == 0):
                        lSegmentCnt.value += 1

                        sys.stdout.write ("Segment[{0:d}] : Minimum: {1:d}, Maximum: {2:d}\n".format (lSegmentCnt.value, lMin, lMax))

                        lMin = 32767
                        lMax = -32768

                spcm_dwSetParam_i32 (hCard, SPC_DATA_AVAIL_CARD_LEN, lNotifySize)

            spcm_dwGetParam_i32 (hCard, SPC_TS_AVAIL_USER_LEN, byref (lAvailUserTS))

            # read timestamp value (1 timestamp = 8 bytes (M2i, M3i) or 16 byte (M4i, M4x, M2p))
            if (lAvailUserTS.value >= lBytesPerTS):

                spcm_dwGetParam_i32 (hCard, SPC_TS_AVAIL_USER_POS, byref (lPCPosTS))

                if ((lPCPosTS.value + lAvailUserTS.value) >= qwBufferSizeTS.value):
                    lAvailUserTS.value = qwBufferSizeTS.value - lPCPosTS.value

                for i in range (0, int (lAvailUserTS.value / lBytesPerTS), 1):

                    # calculate current timestamp buffer index
                    lIndex = int (lPCPosTS.value / 8) + i * int (lBytesPerTS / 8)

                    # calculate timestamp value
                    timestampVal = pllData[lIndex] / llSamplingrate.value

                    # write timestamp value to file
                    fileTS.write (str (timestampVal) + "\n")

                spcm_dwSetParam_i32 (hCard, SPC_TS_AVAIL_CARD_LEN, lAvailUserTS.value)

# send stop command
dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)

fileTS.close ()

sys.stdout.write ("Finished...\n");

# clean up
spcm_vClose (hCard)
