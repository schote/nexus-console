#
# **************************************************************************
#
# simple_rec_single.py                                      (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for all SpcMDrv based analog acquisition cards. 
#
# Information about the different products and their drivers can be found
# online in the Knowledge Base:
# https://www.spectrum-instrumentation.com/en/platform-driver-and-series-differences
#
# Shows a simple Standard mode example using only the few necessary commands
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

import sys

# import spectrum driver functions
from pyspcm import *
from spcm_tools import *

#
# **************************************************************************
# main 
# **************************************************************************
#

szErrorTextBuffer = create_string_buffer (ERRORTEXTLEN)
dwError = uint32 ();
lStatus = int32 ()
lAvailUser = int32 ()
lPCPos = int32 ()
qwTotalMem = uint64 (0);
qwToTransfer = uint64 (MEGA_B(8));


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

sCardName = szTypeToName (lCardType.value)
if lFncType.value == SPCM_TYPE_AI:
    sys.stdout.write("Found: {0} sn {1:05d}\n".format(sCardName,lSerialNumber.value))
else:
    sys.stdout.write("This is an example for A/D cards.\nCard: {0} sn {1:05d} not supported by example\n".format(sCardName,lSerialNumber.value))
    spcm_vClose (hCard)
    exit (1) 

# determine the number of channels on the card
lNumModules = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_MIINST_MODULES, byref (lNumModules));
lNumChPerModule = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_MIINST_CHPERMODULE, byref (lNumChPerModule));
lNumChOnCard = int32 (0)
lNumChOnCard = lNumModules.value * lNumChPerModule.value

# do a simple standard setup
spcm_dwSetParam_i32 (hCard, SPC_CHENABLE,       (1 << lNumChOnCard) - 1)# enable all channels on card
spcm_dwSetParam_i32 (hCard, SPC_MEMSIZE,        16384)                  # acquire 16 kS in total
spcm_dwSetParam_i32 (hCard, SPC_POSTTRIGGER,    8192)                   # half of the total number of samples after trigger event
spcm_dwSetParam_i32 (hCard, SPC_CARDMODE,       SPC_REC_STD_SINGLE)     # single trigger standard mode
spcm_dwSetParam_i32 (hCard, SPC_TIMEOUT,        5000)                   # timeout 5 s
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,    SPC_TMASK_SOFTWARE)     # trigger set to software
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ANDMASK,   0)                      # ...
spcm_dwSetParam_i32 (hCard, SPC_CLOCKMODE,      SPC_CM_INTPLL)          # clock mode internal PLL

lSetChannels = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_CHCOUNT,     byref (lSetChannels))      # get the number of activated channels
bBothModulesUsed = True                                                 # for M2i the data sorting depends on the enabled channels. Here we use a static value for simplicity

# setup the channels
for lChannel in range (0, lSetChannels.value, 1):
    spcm_dwSetParam_i64 (hCard, SPC_AMP0 + lChannel * (SPC_AMP1 - SPC_AMP0),  int32 (1000)) # set input range to +/- 1000 mV

# we try to set the samplerate to 100 kHz (M2i) or 20 MHz on internal PLL, no clock output
if ((lCardType.value & TYP_SERIESMASK) == TYP_M2ISERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M2IEXPSERIES):
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, KILO(100))
else:
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(20))

spcm_dwSetParam_i32 (hCard, SPC_CLOCKOUT, 0)                            # no clock output

# settings for the DMA buffer
qwBufferSize = uint64 (16384 * 2 * lSetChannels.value) # in bytes. Enough memory for 16384 samples with 2 bytes each, all channels active
lNotifySize = int32 (0) # driver should notify program after all data has been transfered


# define the data buffer
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
    

spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, lNotifySize, pvBuffer, uint64 (0), qwBufferSize)

# start card and DMA
dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER | M2CMD_DATA_STARTDMA)

# check for error
if dwError != 0: # != ERR_OK
    spcm_dwGetErrorInfo_i32 (hCard, None, None, szErrorTextBuffer)
    sys.stdout.write("{0}\n".format(szErrorTextBuffer.value))
    spcm_vClose (hCard)
    exit (1)

# wait until acquisition has finished, then calculated min and max
else:
    # arrays for minimum and maximum for each channel
    alMin = [32767] * lSetChannels.value  # normal python type
    alMax = [-32768] * lSetChannels.value # normal python type

    alSamplePos= [] # array for the position of each channel inside one sample
    if (((lCardType.value & TYP_SERIESMASK) == TYP_M2ISERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M2IEXPSERIES)) and bBothModulesUsed:
        # on M2i cards the samples for the channels are multiplexed if channels on both modules are active
        for lChannel in range (0, lSetChannels.value // 2, 1):
            alSamplePos.append (lChannel) # 
            alSamplePos.append (lChannel + lSetChannels.value // 2) # 
    else:
        # starting with M3i all cards use linear sorting of the channels
        for lChannel in range (0, lSetChannels.value, 1):
            alSamplePos.append (lChannel)

    dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_WAITREADY | M2CMD_DATA_WAITDMA)
    if dwError != ERR_OK:
        if dwError == ERR_TIMEOUT:
            sys.stdout.write ("... Timeout\n")
        else:
            sys.stdout.write ("... Error: {0:d}\n".format(dwError))

    else:
        spcm_dwGetParam_i32 (hCard, SPC_M2STATUS,            byref (lStatus))
        spcm_dwGetParam_i32 (hCard, SPC_DATA_AVAIL_USER_LEN, byref (lAvailUser))
        spcm_dwGetParam_i32 (hCard, SPC_DATA_AVAIL_USER_POS, byref (lPCPos))

        qwTotalMem.value = lAvailUser.value
        sys.stdout.write ("Stat:{0:08x} Pos:{1:08x} Avail:{2:08x} Total:{3:.2f}MB/{4:.2f}MB\n".format(lStatus.value, lPCPos.value, lAvailUser.value, c_double (qwTotalMem.value).value / MEGA_B(1), c_double (qwToTransfer.value).value / MEGA_B(1)))

        # this is the point to do anything with the data
        # e.g. calculate minimum and maximum of the acquired data
        lBitsPerSample = int32 (0)
        spcm_dwGetParam_i32 (hCard, SPC_MIINST_BITSPERSAMPLE, byref (lBitsPerSample))
        if lBitsPerSample.value <= 8:
            pbyData = cast  (pvBuffer, ptr8) # cast to pointer to 8bit integer
            for i in range (0, 16383, 1):
                for lChannel in range (0, lSetChannels.value, 1):
                    lDataPos = i * lSetChannels.value + alSamplePos[lChannel]
                    if pbyData[lDataPos] < alMin[lChannel]:
                        alMin[lChannel] = pbyData[lDataPos]
                    if pbyData[lDataPos] > alMax[lChannel]:
                        alMax[lChannel] = pbyData[lDataPos]
        else:
            pnData = cast  (pvBuffer, ptr16) # cast to pointer to 16bit integer
            for i in range (0, 16383, 1):
                for lChannel in range (0, lSetChannels.value, 1):
                    lDataPos = i * lSetChannels.value + alSamplePos[lChannel]
                    if pnData[lDataPos] < alMin[lChannel]:
                        alMin[lChannel] = pnData[lDataPos]
                    if pnData[lDataPos] > alMax[lChannel]:
                        alMax[lChannel] = pnData[lDataPos]

        sys.stdout.write ("Finished...\n");
        for lChannel in range (0, lSetChannels.value, 1):
            sys.stdout.write ("Channel {0:d}\n".format (lChannel)) 
            sys.stdout.write ("\tMinimum: {0:d}\n".format(alMin[lChannel]))
            sys.stdout.write ("\tMaximum: {0:d}\n".format(alMax[lChannel]))


# clean up
spcm_vClose (hCard)

