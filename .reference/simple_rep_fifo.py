#
# **************************************************************************
#
# simple_rep_fifo.py                                       (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for all SpcMDrv based analog replay cards. 
# Shows a simple FIFO mode example using only the few necessary commands
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
import math
import sys
import ctypes

# to speed up the calculation of new data we pre-calculate the signals
# to simplify that we use special frequencies
adSignalFrequency_Hz = [ 40000, 20000, 10000, 5000, 2500, 1250, 625, 312.5 ]

# these will hold the pre-calculated data
lPreCalcLen = int(0) # in samples

def vCalcNewData (pnBuffer, lNumCh, llSamplePos, llNumSamples):
    lStartPosInBuffer_bytes = (llSamplePos % lPreCalcLen) * 2 * lNumCh
    lToCopy_bytes = llNumSamples * 2 * lNumCh
    lPreCalcLen_bytes = lPreCalcLen * 2 * lNumCh
    lAlreadyCopied_bytes = 0
    while lAlreadyCopied_bytes < lToCopy_bytes:
        # copy at most the pre-calculated data
        lCopy_bytes = lToCopy_bytes - lAlreadyCopied_bytes
        if lCopy_bytes > lPreCalcLen_bytes - lStartPosInBuffer_bytes:
            lCopy_bytes = lPreCalcLen_bytes - lStartPosInBuffer_bytes

        # copy data from pre-calculated buffer to DMA buffer
        ctypes.memmove (cast (pnBuffer, c_void_p).value + lAlreadyCopied_bytes, cast (pnPreCalculated, c_void_p).value + lStartPosInBuffer_bytes, lCopy_bytes)
        lAlreadyCopied_bytes += lCopy_bytes
        lStartPosInBuffer_bytes = 0

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
if lFncType.value == SPCM_TYPE_AO:
    sys.stdout.write("Found: {0} sn {1:05d}\n".format(sCardName,lSerialNumber.value))
else:
    sys.stdout.write("This is an example for D/A cards.\nCard: {0} sn {1:05d} not supported by example\n".format(sCardName,lSerialNumber.value))
    spcm_vClose (hCard);
    exit (1)


# set samplerate to 1 MHz (M2i) or 50 MHz, no clock output
if ((lCardType.value & TYP_SERIESMASK) == TYP_M4IEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M4XEXPSERIES):
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(50))
else:
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(1))
spcm_dwSetParam_i32 (hCard, SPC_CLOCKOUT,   0)

# driver might have adjusted the sampling rate to the best-matching value, so we work with that value
llSetSamplerate = int64 (0)
spcm_dwGetParam_i64 (hCard, SPC_SAMPLERATE, byref (llSetSamplerate))

# setup the mode
qwChEnable = uint64 (CHANNEL0 | CHANNEL1)
spcm_dwSetParam_i32 (hCard, SPC_CARDMODE,    SPC_REP_FIFO_SINGLE)
spcm_dwSetParam_i64 (hCard, SPC_CHENABLE,    qwChEnable)
spcm_dwSetParam_i64 (hCard, SPC_SEGMENTSIZE, 4096) # used to limit amount of replayed data if SPC_LOOPS != 0 
spcm_dwSetParam_i64 (hCard, SPC_LOOPS,       0) # continuous replay

lSetChannels = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_CHCOUNT, byref (lSetChannels))
lBytesPerSample = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_MIINST_BYTESPERSAMPLE,  byref (lBytesPerSample))

# create a buffer a pre-calculate the signal because calculation on-the-fly is way too slow
lPreCalcLen = int(llSetSamplerate.value / adSignalFrequency_Hz[lSetChannels.value - 1]) # max length of all channels
pnPreCalculated = ptr16 (pvAllocMemPageAligned (lPreCalcLen * lSetChannels.value * 2)) # buffer for pre-calculated and muxed data
sys.stdout.write("Len: {0} Buf: {1}\n".format(lPreCalcLen,pnPreCalculated))
for lChIdx in range (0, lSetChannels.value):
    for i in range (0, lPreCalcLen):
        pnPreCalculated[lSetChannels.value * i + lChIdx] = int16(int(32767 * math.sin (2.*math.pi*(i)/(llSetSamplerate.value / adSignalFrequency_Hz[lChIdx]))))

# setup the trigger mode
# (SW trigger, no output)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,      SPC_TMASK_SOFTWARE)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ANDMASK,     0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ORMASK0,  0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ORMASK1,  0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ANDMASK0, 0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ANDMASK1, 0)
spcm_dwSetParam_i32 (hCard, SPC_TRIGGEROUT,       0)

# setup all channels
for i in range (0, lSetChannels.value):
    spcm_dwSetParam_i32 (hCard, SPC_AMP0 + i * (SPC_AMP1 - SPC_AMP0), int32 (1000))
    spcm_dwSetParam_i32 (hCard, SPC_ENABLEOUT0 + i * (SPC_ENABLEOUT1 - SPC_ENABLEOUT0),  int32(1))

# setup software buffer
lNotifySize_bytes = int32(128 * 1024) # 128 kB
qwBufferSize = uint64 (32*1024*1024) # 32 MByte. For simplicity qwBufferSize should be a multiple of lNotifySize_bytes
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
# we calculate data for all enabled channels, starting at sample position 0, and fill the complete DMA buffer
qwSamplePos = 0
lNumAvailSamples = (qwBufferSize.value // lSetChannels.value) // lBytesPerSample.value
vCalcNewData (pvBuffer, lSetChannels.value, qwSamplePos, lNumAvailSamples)
qwSamplePos += lNumAvailSamples

# we define the buffer for transfer and start the DMA transfer
sys.stdout.write("Starting the DMA transfer and waiting until data is in board memory\n")
spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, lNotifySize_bytes, pvBuffer, uint64 (0), qwBufferSize)
spcm_dwSetParam_i32 (hCard, SPC_DATA_AVAIL_CARD_LEN, qwBufferSize)

spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_DATA_STARTDMA)

# We'll start the replay and run until a timeout occurs or user interrupts the program
lStatus = int32(0)
lAvailUser_bytes = int32(0)
lPCPos = int32(0)
lFillsize = int32 (0)
bStarted = False
acRunIndicator = [ '.', 'o', 'O', 'o' ]
lRunIndicatorIdx = 0
while True:
    dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_DATA_WAITDMA)
    if dwError != ERR_OK:
        if dwError == ERR_TIMEOUT:
            sys.stdout.write ("\n... Timeout\n")
        else:
            szErrorTextBuffer = create_string_buffer (ERRORTEXTLEN)
            spcm_dwGetErrorInfo_i32 (hCard, None, None, szErrorTextBuffer)
            sys.stdout.write ("\n... Error: {0}\n".format(szErrorTextBuffer.value))
            break;

    else:
        # start the card if the onboard buffer has been filled completely
        spcm_dwGetParam_i32 (hCard, SPC_FILLSIZEPROMILLE, byref (lFillsize));
        if lFillsize.value == 1000 and bStarted == False:
            sys.stdout.write("... data has been transferred to board memory\n")
            sys.stdout.write("\nStarting the card...\n")
            dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER)
            if dwError == ERR_TIMEOUT:
                spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_STOP)
                sys.stdout.write ("... Timeout at start\n")
                break;
            bStarted = True
        else:
            # print the fill size and a indicator to show that the program is still running
            # change indicator every 25 loops to get nice update rate
            sys.stdout.write ("\r... Fillsize: {0:d}/1000 {1}".format(lFillsize.value, acRunIndicator[lRunIndicatorIdx // 25]))
            lRunIndicatorIdx = (lRunIndicatorIdx + 1) % (len (acRunIndicator) * 25)

        spcm_dwGetParam_i32 (hCard, SPC_M2STATUS,            byref (lStatus))
        spcm_dwGetParam_i32 (hCard, SPC_DATA_AVAIL_USER_LEN, byref (lAvailUser_bytes))
        spcm_dwGetParam_i32 (hCard, SPC_DATA_AVAIL_USER_POS, byref (lPCPos))

        # calculate new data
        if lAvailUser_bytes.value >= lNotifySize_bytes.value:
            pnData = (c_char * (qwBufferSize.value - lPCPos.value)).from_buffer (pvBuffer, lPCPos.value)
            lNumAvailSamples = (lNotifySize_bytes.value // lSetChannels.value) // lBytesPerSample.value # to avoid problems with buffer wrap-arounds we fill only one notify size
            vCalcNewData (pnData, lSetChannels.value, qwSamplePos, lNumAvailSamples)
            spcm_dwSetParam_i32 (hCard, SPC_DATA_AVAIL_CARD_LEN, lNotifySize_bytes)
            qwSamplePos += lNumAvailSamples

# send the stop command
dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)

spcm_vClose (hCard);

