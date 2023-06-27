#
# **************************************************************************
#
# simple_sync_rep_single.py                                (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for two synchronized SpcMDrv based analog replay cards.
# Shows a simple standard mode example using only the few necessary commands.
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
from math import sin
from math import pi

#
# **************************************************************************
# main 
# **************************************************************************
#

# open cards
listhCards = []
for i in range (0, 2):
    # open card
    # uncomment the second pair of lines and replace the IP address to use remote
    # cards like in a generatorNETBOX
    p = create_string_buffer (b'/dev/spcm', 12);
    p[9] = 48 + i # '0' + i => '0', '1', '2', ...
    #p = create_string_buffer (b'TCPIP::192.168.1.10::instX::INSTR')
    #p[p.value.index (b'X')] = 48 + i # 'X' => '0', '1', '2', ...
    sys.stdout.write ("Opening {0}\n".format (p.value))
    hCard = spcm_hOpen (p)
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
        sys.stdout.write("This is an example for D/A cards.\nCard: {0} sn {1:05d} not supported by this example\n".format(sCardName,lSerialNumber.value))
        spcm_vClose (hCard)
        for hPrevCard in listhCards:
            spcm_vClose (hPrevCard)
        exit (1)

    listhCards += [hCard]

# open handle for star-hub
hSync = spcm_hOpen (create_string_buffer (b'sync0'))
if hSync == None:
    sys.stdout.write("Could not open star-hub...\n")
    for hCard in listhCards:
        spcm_vClose (hCard)
    exit (1)


# setup star-hub
nCardCount = len (listhCards)
spcm_dwSetParam_i32 (hSync, SPC_SYNC_ENABLEMASK, (1 << nCardCount) - 1)


# do a simple setup in CONTINUOUS replay mode for each card
llMemSamples = int64 (KILO_B(64))
llLoops = int64 (0) # loop continuously
i = 0
for hCard in listhCards:
    # set samplerate to 1 MHz (M2i, M2p) or 50 MHz (M4i, M4x), no clock output
    if ((lCardType.value & TYP_SERIESMASK) == TYP_M4IEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M4XEXPSERIES):
        spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(50))
    else:
        spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(1))
    spcm_dwSetParam_i32 (hCard, SPC_CLOCKOUT,   0)

    # calculate the number of channels on this card
    lNumModules = int32 (0)
    lNumChPerModule = int32 (0)
    lNumChOnCard = int32 (0)
    spcm_dwGetParam_i32 (hCard, SPC_MIINST_MODULES,     byref (lNumModules))
    spcm_dwGetParam_i32 (hCard, SPC_MIINST_CHPERMODULE, byref (lNumChPerModule))
    lNumChOnCard = lNumModules.value * lNumChPerModule.value

    # setup the mode
    spcm_dwSetParam_i32 (hCard, SPC_CARDMODE,    SPC_REP_STD_CONTINUOUS)
    spcm_dwSetParam_i64 (hCard, SPC_CHENABLE,    (1 << lNumChOnCard) - 1) # enable all channels
    spcm_dwSetParam_i64 (hCard, SPC_MEMSIZE,     llMemSamples)
    spcm_dwSetParam_i64 (hCard, SPC_LOOPS,       llLoops)

    lSetChannels = int32 (0)
    spcm_dwGetParam_i32 (hCard, SPC_CHCOUNT,     byref (lSetChannels))
    lBytesPerSample = int32 (0)
    spcm_dwGetParam_i32 (hCard, SPC_MIINST_BYTESPERSAMPLE,  byref (lBytesPerSample))

    # setup the trigger mode
    # (SW trigger, no output)
    lFeatures = int32 (0)
    spcm_dwGetParam_i32 (hCard, SPC_PCIFEATURES, byref (lFeatures))
    if (lFeatures.value & (SPCM_FEAT_STARHUB5 | SPCM_FEAT_STARHUB16)):
        # set star-hub carrier card as clock master and trigger master
        spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,  SPC_TMASK_SOFTWARE)
        spcm_dwSetParam_i32 (hSync, SPC_SYNC_CLKMASK, (1 << i))
    else:
        spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,  SPC_TMASK_NONE)
    spcm_dwSetParam_i32 (hCard, SPC_TRIG_ANDMASK,     0)
    spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ORMASK0,  0)
    spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ORMASK1,  0)
    spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ANDMASK0, 0)
    spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ANDMASK1, 0)
    spcm_dwSetParam_i32 (hCard, SPC_TRIGGEROUT,       0)

    # setup the channels
    for lChannel in range (0, lSetChannels.value, 1):
        spcm_dwSetParam_i64 (hCard, SPC_ENABLEOUT0 + lChannel * (SPC_ENABLEOUT1 - SPC_ENABLEOUT0),  int32 (1))
        spcm_dwSetParam_i32 (hCard, SPC_AMP0       + lChannel * (SPC_AMP1       - SPC_AMP0),        int32 (1000))

    # setup software buffer
    qwBufferSize = uint64 (llMemSamples.value * lBytesPerSample.value * lSetChannels.value)
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

    lMaxDACValue = int32 (0)
    spcm_dwGetParam_i32 (hCard, SPC_MIINST_MAXADCVALUE, byref(lMaxDACValue))
    lMaxDACValue.value = lMaxDACValue.value - 1

    # calculate the data
    pnBuffer = cast  (pvBuffer, ptr16)
    if i == 0: 
        # first card, generate a sine on each channel
        for lSampleIdx in range (0, llMemSamples.value, 1):
            for lChIdx in range (0, lSetChannels.value, 1):
                dFactor = sin(2 * pi * lSampleIdx / (llMemSamples.value / (lChIdx + 1)))
                pnBuffer[lSampleIdx*lSetChannels.value + lChIdx] = int(lMaxDACValue.value * dFactor)
    elif i == 1:
        # second card, generate a rising ramp on each channel
        for lSampleIdx in range (0, llMemSamples.value, 1):
            for lChIdx in range (0, lSetChannels.value, 1):
                dFactor = lSampleIdx / (llMemSamples.value / (lChIdx + 1))
                pnBuffer[lSampleIdx*lSetChannels.value + lChIdx] = int(lMaxDACValue.value * dFactor)
    elif i == 2:
        # third card, generate a rectangle on each channel
        for lSampleIdx in range (0, llMemSamples.value, 1):
            for lChIdx in range (0, lSetChannels.value, 1):
                if lSampleIdx < ((llMemSamples.value / 2) / (lChIdx + 1)):
                    dFactor = 1
                else:
                    dFactor = -1
                pnBuffer[lSampleIdx*lSetChannels.value + lChIdx] = int(lMaxDACValue.value * dFactor)
    elif i == 3:
        # fourth card, generate a falling ramp on each channel
        for lSampleIdx in range (0, llMemSamples.value, 1):
            for lChIdx in range (0, lSetChannels.value, 1):
                dFactor = 1.0 - lSampleIdx / (llMemSamples.value / (lChIdx + 1))
                pnBuffer[lSampleIdx*lSetChannels.value + lChIdx] = int(lMaxDACValue.value * dFactor)
        

    # we define the buffer for transfer and start the DMA transfer
    sys.stdout.write("Starting the DMA transfer and waiting until data is in board memory\n")
    spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), pvBuffer, uint64 (0), qwBufferSize)
    spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
    sys.stdout.write("... data has been transferred to board memory\n")

    spcm_dwSetParam_i32 (hCard, SPC_TIMEOUT, 10000)

    i += 1


# We'll start and wait until the card has finished or until a timeout occurs
# since the card is running in SPC_REP_STD_CONTINUOUS mode with SPC_LOOPS = 0 we will see the timeout
sys.stdout.write("\nStarting the card and waiting for ready interrupt\n(continuous and single restart will have timeout)\n")
dwError = spcm_dwSetParam_i32 (hSync, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER | M2CMD_CARD_WAITREADY)
if dwError == ERR_TIMEOUT:
    spcm_dwSetParam_i32 (hSync, SPC_M2CMD, M2CMD_CARD_STOP)

# close sync handle
spcm_vClose (hSync)

# close all cards
for hCard in listhCards:
    spcm_vClose (hCard)

