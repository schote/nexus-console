#
# **************************************************************************
#
# simple_sync_rec_fifo.py                                  (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for two synchronized SpcMDrv based analog acquisition cards.
#
# Information about the different products and their drivers can be found
# online in the Knowledge Base:
# https://www.spectrum-instrumentation.com/en/platform-driver-and-series-differences
#
# Shows a simple multi-threaded FIFO mode example using only the
# few necessary commands. The example uses only minimal error handling
# to simplify the code.
#
# Feel free to use this source for own projects and modify it in any kind.
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
import threading 

# import spectrum driver functions
from pyspcm import *
from spcm_tools import *

#
# **************************************************************************
# CardThread: thread that handles the data transfer for a card
# One instance will be started for each card.
# **************************************************************************
#

class CardThread (threading.Thread): 
  def __init__ (self, dwIdx, hCard, pvBuffer):
    threading.Thread.__init__ (self)
    self.m_dwIdx    = dwIdx     # index of card (only used for output)
    self.m_hCard    = hCard     # handle to the card
    self.m_pvBuffer = pvBuffer  # DMA buffer for the card

  def run (self):
    lMin = int (32767)  # normal python type
    lMax = int (-32768) # normal python type
    lStatus = int32 ()
    lAvailUser = int32 ()
    lPCPos = int32 ()

    qwToTransfer = uint64 (MEGA_B(8)); # card will be stopped after this amount of data has been transfered
    qwTotalMem = uint64 (0);           # counts amount of already transfered data
    while qwTotalMem.value < qwToTransfer.value:
        dwError = spcm_dwSetParam_i32 (self.m_hCard, SPC_M2CMD, M2CMD_DATA_WAITDMA)
        if dwError != ERR_OK:
            if dwError == ERR_TIMEOUT:
                sys.stdout.write ("{0} ... Timeout\n".format (self.m_dwIdx))
            else:
                sys.stdout.write ("{0} ... Error: {1:d}\n".format (self.m_dwIdx, dwError))
                break;

        else:
            # get status and amount of available data
            spcm_dwGetParam_i32 (self.m_hCard, SPC_M2STATUS,            byref (lStatus))
            spcm_dwGetParam_i32 (self.m_hCard, SPC_DATA_AVAIL_USER_LEN, byref (lAvailUser))
            spcm_dwGetParam_i32 (self.m_hCard, SPC_DATA_AVAIL_USER_POS, byref (lPCPos))

            if lAvailUser.value >= lNotifySize.value:
                qwTotalMem.value += lNotifySize.value
                sys.stdout.write ("{0} Stat:{1:08x} Pos:{2:08x} Avail:{3:08x} Total:{4:.2f}MB/{5:.2f}MB\n".format(self.m_dwIdx, lStatus.value, lPCPos.value, lAvailUser.value, c_double (qwTotalMem.value).value / MEGA_B(1), c_double (qwToTransfer.value).value / MEGA_B(1)))

                # this is the point to do anything with the data
                # e.g. calculate minimum and maximum of the acquired data
                pnData = cast (addressof (self.m_pvBuffer) + lPCPos.value, ptr16) # cast to pointer to 16bit integer
                lNumSamples = int (lNotifySize.value / 2) # two bytes per sample
                for i in range (0, lNumSamples - 1, 1):
                    if pnData[i] < lMin:
                        lMin = pnData[i]
                    if pnData[i] > lMax:
                        lMax = pnData[i]

                # mark buffer space as available again
                spcm_dwSetParam_i32 (self.m_hCard, SPC_DATA_AVAIL_CARD_LEN, lNotifySize)

    # send the stop command
    dwError = spcm_dwSetParam_i32 (self.m_hCard, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)

    # print the calculated results
    sys.stdout.write ("{0} Finished...\n".format (self.m_dwIdx))
    sys.stdout.write ("{0} Minimum: {1:d}\n".format (self.m_dwIdx, lMin))
    sys.stdout.write ("{0} Maximum: {1:d}\n".format (self.m_dwIdx, lMax))



#
# **************************************************************************
# main 
# **************************************************************************
#

szErrorTextBuffer = create_string_buffer (ERRORTEXTLEN)
dwError = uint32 ();

# settings for the FIFO mode buffer handling
qwBufferSize = uint64 (MEGA_B(4));
lNotifySize = int32 (KILO_B(16));

# open cards
listhCards = []
for i in xrange (0, 2):
    # open card
    # uncomment the second line and replace the IP address to use remote
    # cards like in a digitizerNETBOX
    if i == 0:
        hCard = spcm_hOpen (create_string_buffer (b'/dev/spcm0'))
        #hCard = spcm_hOpen (create_string_buffer (b'TCPIP::192.168.1.10::inst0::INSTR'))
    else:
        hCard = spcm_hOpen (create_string_buffer (b'/dev/spcm1'))
        #hCard = spcm_hOpen (create_string_buffer (b'TCPIP::192.168.1.10::inst1::INSTR'))
    if hCard == None:
        sys.stdout.write("card not found...\n")
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


# do a simple FIFO setup for each card
listpvBuffers = []
for hCard in listhCards:
    spcm_dwSetParam_i32 (hCard, SPC_CHENABLE,       1)                      # just 1 channel enabled
    spcm_dwSetParam_i32 (hCard, SPC_PRETRIGGER,     1024)                   # 1k of pretrigger data at start of FIFO mode
    spcm_dwSetParam_i32 (hCard, SPC_CARDMODE,       SPC_REC_FIFO_SINGLE)    # single FIFO mode
    spcm_dwSetParam_i32 (hCard, SPC_TIMEOUT,        5000)                   # timeout 5 s
    spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,    SPC_TMASK_SOFTWARE)     # trigger set to software
    spcm_dwSetParam_i32 (hCard, SPC_TRIG_ANDMASK,   0)                      # ...
    spcm_dwSetParam_i32 (hCard, SPC_CLOCKMODE,      SPC_CM_INTPLL)          # clock mode internal PLL

    # we try to set the samplerate to 100 kHz (M2i) or 20 MHz (M3i/M4i) on internal PLL, no clock output
    if ((lCardType.value & TYP_SERIESMASK) == TYP_M2ISERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M2IEXPSERIES):
        spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, KILO(100))
    else:
        spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(20))

    spcm_dwSetParam_i32 (hCard, SPC_CLOCKOUT, 0)                            # no clock output

    # define the data buffer
    # we try to use continuous memory if available and big enough
    pvBuffer = ptr8 () # will be cast to correct type later on
    qwContBufLen = uint64 (0)
    spcm_dwGetContBuf_i64 (hCard, SPCM_BUF_DATA, byref(pvBuffer), byref(qwContBufLen))
    sys.stdout.write ("ContBuf length: {0:d}\n".format(qwContBufLen.value))
    if qwContBufLen.value >= qwBufferSize.value:
        sys.stdout.write("Using continuous buffer\n")
    else:
        pvBuffer = cast (pvAllocMemPageAligned (qwBufferSize.value), ptr8) # cast to ptr8 to make it behave like the continuous memory
        sys.stdout.write("Using buffer allocated by user program\n")

    spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, lNotifySize, pvBuffer, uint64 (0), qwBufferSize)
    listpvBuffers += [pvBuffer]


# setup star-hub
nCardCount = len (listhCards)
spcm_dwSetParam_i32 (hSync, SPC_SYNC_ENABLEMASK, (1 << nCardCount) - 1)

# find star-hub carrier card and set it as clock master
i = 0
for hCard in listhCards:
    lFeatures = int32 (0)
    spcm_dwGetParam_i32 (hCard, SPC_PCIFEATURES, byref (lFeatures))
    if (lFeatures.value & (SPCM_FEAT_STARHUB5 | SPCM_FEAT_STARHUB16)):
        break
    i += 1
spcm_dwSetParam_i32 (hSync, SPC_SYNC_CLKMASK, (1 << i))


# start all cards using the star-hub handle
dwError = spcm_dwSetParam_i32 (hSync, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER | M2CMD_DATA_STARTDMA)
if dwError != 0: # != ERR_OK
    spcm_dwGetErrorInfo_i32 (hSync, None, None, szErrorTextBuffer)
    sys.stdout.write("{0}\n".format(szErrorTextBuffer.value))
    spcm_vClose (hSync)
    for hCard in listhCards:
        spcm_vClose (hCard)
    exit (1)

 
# for each card we start a thread that controls the data transfer
listThreads = [] 
i = 0
for hCard in listhCards:
    thread = CardThread(i, hCard, listpvBuffers[i]) 
    listThreads += [thread] 
    thread.start () 
    i = i + 1
 
# wait until all threads have finished
for x in listThreads: 
    x.join ()


# close sync handle
spcm_vClose (hSync)

# close all cards
for hCard in listhCards:
    spcm_vClose (hCard)

