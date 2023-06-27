#
# **************************************************************************
#
# simple_rep_single.py                                     (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for all SpcMDrv based analog replay cards as well as digital output
# and digital I/O cards. 
# Shows a simple standard mode example using only the few necessary commands
#
# Information about the different products and their drivers can be found
# online in the Knowledge Base:
# https://www.spectrum-instrumentation.com/en/platform-driver-and-series-differences
#
# Feel free to use this source for own projects and modify it in any kind
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


from pyspcm import *
from spcm_tools import *
import sys

#
# **************************************************************************
# main 
# **************************************************************************
#

# open card
# uncomment the second line and replace the IP address to use remote
# cards like in a generatorNETBOX
hCard = spcm_hOpen (create_string_buffer (b'/dev/spcm0'))
#hCard = spcm_hOpen (create_string_buffer (b'TCPIP::192.168.1.10::inst0::INSTR'))
if hCard == None:
    sys.stdout.write("no card found...\n")
    exit (1)


# read type, function and sn and check for D/A card
lCardType = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_PCITYP, byref (lCardType))
lSerialNumber = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_PCISERIALNO, byref (lSerialNumber))
lFncType = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_FNCTYPE, byref (lFncType))

sCardName = szTypeToName (lCardType.value)
if lFncType.value == SPCM_TYPE_AO or lFncType.value == SPCM_TYPE_DO or lFncType.value == SPCM_TYPE_DIO:
    sys.stdout.write("Found: {0} sn {1:05d}\n".format(sCardName,lSerialNumber.value))
else:
    sys.stdout.write("This is an example for analog output, digital output and digital I/O cards.\nCard: {0} sn {1:05d} not supported by example\n".format(sCardName,lSerialNumber.value))
    spcm_vClose (hCard);
    exit (1)


# set samplerate to 1 MHz (M2i) or 50 MHz, no clock output
if ((lCardType.value & TYP_SERIESMASK) == TYP_M4IEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M4XEXPSERIES):
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(50))
else:
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(1))
spcm_dwSetParam_i32 (hCard, SPC_CLOCKOUT,   0)

# setup the mode
if lFncType.value == SPCM_TYPE_AO:
    qwChEnable = uint64 (1)
else:
    qwChEnable = 0xFFFFFFFF # enable 32 channels
llMemSamples = int64 (KILO_B(64))
llLoops = int64 (0) # loop continuously
spcm_dwSetParam_i32 (hCard, SPC_CARDMODE,    SPC_REP_STD_CONTINUOUS)
spcm_dwSetParam_i64 (hCard, SPC_CHENABLE,    qwChEnable)
spcm_dwSetParam_i64 (hCard, SPC_MEMSIZE,     llMemSamples)
spcm_dwSetParam_i64 (hCard, SPC_LOOPS,       llLoops)

lSetChannels = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_CHCOUNT,     byref (lSetChannels))
lBytesPerSample = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_MIINST_BYTESPERSAMPLE,  byref (lBytesPerSample))

# setup the trigger mode
# (SW trigger, no output)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,      SPC_TMASK_SOFTWARE)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ANDMASK,     0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ORMASK0,  0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ORMASK1,  0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ANDMASK0, 0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ANDMASK1, 0)
spcm_dwSetParam_i32 (hCard, SPC_TRIGGEROUT,       0)

# setup the analog output channels
if lFncType.value == SPCM_TYPE_AO:
    lChannel = int32 (0)
    spcm_dwSetParam_i32 (hCard, SPC_AMP0 + lChannel.value * (SPC_AMP1 - SPC_AMP0), int32 (1000))
    spcm_dwSetParam_i64 (hCard, SPC_ENABLEOUT0 + lChannel.value * (SPC_ENABLEOUT1 - SPC_ENABLEOUT0), int32 (1))

# setup software buffer
if lFncType.value == SPCM_TYPE_AO:
    qwBufferSize = uint64 (llMemSamples.value * lBytesPerSample.value * lSetChannels.value)
else:
    qwBufferSize = uint64 (llMemSamples.value * lSetChannels.value // 8) # eight channels per byte for DO and DIO cards
# we try to use continuous memory if available and big enough
pvBuffer = c_void_p ()
qwContBufLen = uint64 (0)
spcm_dwGetContBuf_i64 (hCard, SPCM_BUF_DATA, byref(pvBuffer), byref(qwContBufLen))
sys.stdout.write ("ContBuf length: {0:d}\n".format(qwContBufLen.value))
if qwContBufLen.value >= qwBufferSize.value:
    sys.stdout.write("Using continuous buffer\n")
else:
    pvBuffer = pvAllocMemPageAligned (qwBufferSize.value)
    sys.stdout.write("Using buffer allocated by user program\n")

# calculate the data
if lFncType.value == SPCM_TYPE_AO:
    # simple ramp for analog output cards
    pnBuffer = cast  (pvBuffer, ptr16)
    for i in range (0, llMemSamples.value, 1):
        pnBuffer[i] = i
else:
    # a tree for digital output cards
    pdwBuffer = cast (pvBuffer, uptr32)
    for i in range (0, llMemSamples.value, 1):
        pdwBuffer[i] = 0x1 << (i % 32)

# we define the buffer for transfer and start the DMA transfer
sys.stdout.write("Starting the DMA transfer and waiting until data is in board memory\n")
spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), pvBuffer, uint64 (0), qwBufferSize)
spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
sys.stdout.write("... data has been transferred to board memory\n")

# We'll start and wait until the card has finished or until a timeout occurs
spcm_dwSetParam_i32 (hCard, SPC_TIMEOUT, 10000)
sys.stdout.write("\nStarting the card and waiting for ready interrupt\n(continuous and single restart will have timeout)\n")
dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER | M2CMD_CARD_WAITREADY)
if dwError == ERR_TIMEOUT:
    spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_STOP)

spcm_vClose (hCard);

