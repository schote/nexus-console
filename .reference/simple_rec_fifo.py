#
# **************************************************************************
#
# simple_rec_fifo.py                                      (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for all SpcMDrv based analog acquisition cards. 
#
# Information about the different products and their drivers can be found
# online in the Knowledge Base:
# https://www.spectrum-instrumentation.com/en/platform-driver-and-series-differences
#
# Shows a simple FIFO mode example using only the few necessary commands
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
import ctypes

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

# settings for the FIFO mode buffer handling
qwBufferSize = uint64 (MEGA_B(1));
#qwBufferSize = uint64 (KILO_B(128));
lNotifySize = int32 (KILO_B(16));


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


# do a simple standard setup
spcm_dwSetParam_i32 (hCard, SPC_CHENABLE,       1)                      # just 1 channel enabled
spcm_dwSetParam_i32 (hCard, SPC_PRETRIGGER,     1024)                   # 1k of pretrigger data at start of FIFO mode
spcm_dwSetParam_i32 (hCard, SPC_CARDMODE,       SPC_REC_FIFO_SINGLE)    # single FIFO mode
spcm_dwSetParam_i32 (hCard, SPC_TIMEOUT,        5000)                   # timeout 5 s
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,    SPC_TMASK_SOFTWARE)     # trigger set to software
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ANDMASK,   0)                      # ...
spcm_dwSetParam_i32 (hCard, SPC_CLOCKMODE,      SPC_CM_INTPLL)          # clock mode internal PLL

lBitsPerSample = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_MIINST_BITSPERSAMPLE, byref (lBitsPerSample))

# we try to set the samplerate to 100 kHz (M2i) or 20 MHz on internal PLL, no clock output
if ((lCardType.value & TYP_SERIESMASK) == TYP_M2ISERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M2IEXPSERIES):
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, KILO(100))
else:
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(20))

spcm_dwSetParam_i32 (hCard, SPC_CLOCKOUT, 0)                            # no clock output


# define the data buffer
# we try to use continuous memory if available and big enough
pvBuffer = ptr8 () # will be cast to correct type later
qwContBufLen = uint64 (0)
spcm_dwGetContBuf_i64 (hCard, SPCM_BUF_DATA, byref(pvBuffer), byref(qwContBufLen))
sys.stdout.write ("ContBuf length: {0:d}\n".format(qwContBufLen.value))
if qwContBufLen.value >= qwBufferSize.value:
    sys.stdout.write("Using continuous buffer\n")
else:
    pvBuffer = cast (pvAllocMemPageAligned (qwBufferSize.value), ptr8) # cast to ptr8 to make it behave like the continuous memory
    sys.stdout.write("Using buffer allocated by user program\n")


spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, lNotifySize, pvBuffer, uint64 (0), qwBufferSize)

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
                sys.stdout.write ("Stat:{0:08x} Pos:{1:08x} Avail:{2:08x} Total:{3:.2f}MB/{4:.2f}MB\n".format(lStatus.value, lPCPos.value, lAvailUser.value, c_double (qwTotalMem.value).value / MEGA_B(1), c_double (qwToTransfer.value).value / MEGA_B(1)))

                # this is the point to do anything with the data
                # e.g. calculate minimum and maximum of the acquired data
                if lBitsPerSample.value <= 8:
                    pbyData = cast  (addressof (pvBuffer.contents) + lPCPos.value, ptr8) # cast to pointer to 8bit integer
                    lNumSamples = int (lNotifySize.value)  # one byte per sample
                    for i in range (0, lNumSamples - 1, 1):
                        if pbyData[i] < lMin:
                            lMin = pbyData[i]
                        if pbyData[i] > lMax:
                            lMax = pbyData[i]
                else:
                    pnData = cast  (addressof (pvBuffer.contents) + lPCPos.value, ptr16) # cast to pointer to 16bit integer
                    lNumSamples = int (lNotifySize.value / 2) # two bytes per sample
                    for i in range (0, lNumSamples - 1, 1):
                        if pnData[i] < lMin:
                            lMin = pnData[i]
                        if pnData[i] > lMax:
                            lMax = pnData[i]

                spcm_dwSetParam_i32 (hCard, SPC_DATA_AVAIL_CARD_LEN,  lNotifySize)

#            # check for escape = abort
#            if (bKbhit())
#                if (cGetch() == 27)
#                    break;


# send the stop command
dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)

sys.stdout.write ("Finished...\n");
sys.stdout.write ("Minimum: {0:d}\n".format(lMin));
sys.stdout.write ("Maximum: {0:d}\n".format(lMax));


# clean up
spcm_vClose (hCard)


