# %%
# **************************************************************************
#
# simple_rep_sequence.py                                   (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for all SpcMDrv based analog replay cards. 
# Shows a simple sequence mode example using only the few necessary commands
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
import math 
from enum import IntEnum

import msvcrt
from time import sleep

USING_EXTERNAL_TRIGGER = False
LAST_STEP_OFFSET = 0
def lKbhit():
    return ord(msvcrt.getch()) if msvcrt.kbhit() else 0
# %%
#
#**************************************************************************
# vWriteSegmentData: transfers the data for a segment to the card's memory
#**************************************************************************
#

def vWriteSegmentData (hCard, lNumActiveChannels, dwSegmentIndex, dwSegmentLenSample, pvSegData):
    lBytesPerSample = 2
    dwSegLenByte = uint32 (dwSegmentLenSample * lBytesPerSample * lNumActiveChannels.value)

    # setup
    dwError = spcm_dwSetParam_i32 (hCard, SPC_SEQMODE_WRITESEGMENT, dwSegmentIndex)
    if dwError == ERR_OK:
        dwError = spcm_dwSetParam_i32 (hCard, SPC_SEQMODE_SEGMENTSIZE,  dwSegmentLenSample)

    # write data to board (main) sample memory
    if dwError == ERR_OK:
        dwError = spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, 0, pvSegData, 0, dwSegLenByte)
    if dwError == ERR_OK:
        dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)



#
#**************************************************************************
# DoDataCalculation: calculates and writes the output data for all segments
#**************************************************************************
#

# (main) sample memory segment index:
class SEGMENT_IDX(IntEnum):
    SEG_RAMPUP   =  0 # ramp up
    SEG_RAMPDOWN =  1 # ramp down
    SEG_SYNC     =  2 # negative sync puls, for example oscilloscope trigger
    #                      3 // unused
    SEG_Q1SIN    =  4 # first quadrant of sine signal
    SEG_Q2SIN    =  5 # second quadrant of sine signal
    SEG_Q3SIN    =  6 # third quadrant of sine signal
    SEG_Q4SIN    =  7 # fourth quadrant of sine signal
    SEG_STOP     =  8 # DC level for stop/end


def vDoDataCalculation (lCardType, lNumActiveChannels, lMaxDACValue):
    dwSegmentLenSample = uint32 (0)
    dwSegLenByte       = uint32 (0)

    sys.stdout.write ("Calculation of output data\n")


    dwFactor = 1
    # This series has a slightly increased minimum size value.
    if ((lCardType.value & TYP_SERIESMASK) == TYP_M4IEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M4XEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M5IEXPSERIES):
        dwFactor = 6

    # buffer for data transfer
    dwSegLenByte = 2 * dwFactor * 512 * lNumActiveChannels.value # max value taken from sine calculation below
    pvBuffer = pvAllocMemPageAligned (dwSegLenByte)
    pnData = cast (addressof (pvBuffer), ptr16)


    # helper values: Full Scale
    dwFS = uint32 (lMaxDACValue.value)
    dwFShalf = uint32 (dwFS.value // 2)


    # !!! to keep the example simple we will generate the same data on all active channels !!!

    # data for the channels is interleaved. This means that we first write the first sample for each
    # of the active channels into the buffer, then the second sample for each channel, and so on
    # Please see the hardware manual, chapte "Data organization" for more information

    # to generate different signals on all channels:
    # for i in range (0, dwSegmentLenSample, 1):
    #    for ch in range (0, lNumActiveChannels.value, 1):
    #        if ch == 0:
    #            # generate a sine wave on channel 0
    #            pnData[i * lNumActiveChannels.value + ch] = int16 (dwFS.value * math.sin (2.0 * math.pi * (i / dwSegmentLenSample) + 0.5))
    #        elif ch == 1:
    #            # generate a ramp on ch1
    #            pnData[i * lNumActiveChannels.value + ch] = int16 (i * dwFS.value // dwSegmentLenSample)
    #        elif ch == 2:
    #            ...
    #
    # using numpy.column_stack is another possibility to interleave the data


    # --- sync puls: first half zero, second half -FS
    dwSegmentLenSample = dwFactor * 80
    for i in range (0, dwSegmentLenSample // 2, 1):
        for ch in range (0, lNumActiveChannels.value, 1):
            pnData[i * lNumActiveChannels.value + ch] = 0
    for i in range (dwSegmentLenSample // 2, dwSegmentLenSample, 1):
        for ch in range (0, lNumActiveChannels.value, 1):
            pnData[i * lNumActiveChannels.value + ch] = -lMaxDACValue.value

    vWriteSegmentData (hCard, lNumActiveChannels, SEGMENT_IDX.SEG_SYNC, dwSegmentLenSample, pvBuffer)


    # --- ramp up
    dwSegmentLenSample = dwFactor * 64
    for i in range (0, dwSegmentLenSample, 1):
        for ch in range (0, lNumActiveChannels.value, 1):
            pnData[i * lNumActiveChannels.value + ch] = int16 (i * dwFShalf.value // dwSegmentLenSample)

    vWriteSegmentData (hCard, lNumActiveChannels, SEGMENT_IDX.SEG_RAMPUP, dwSegmentLenSample, pvBuffer)


    # --- ramp down
    dwSegmentLenSample = dwFactor * 64
    for i in range (0, dwSegmentLenSample, 1):
        for ch in range (0, lNumActiveChannels.value, 1):
            pnData[i * lNumActiveChannels.value + ch] = int16 (dwFS.value - (i * dwFShalf.value // dwSegmentLenSample))

    vWriteSegmentData (hCard, lNumActiveChannels, SEGMENT_IDX.SEG_RAMPDOWN, dwSegmentLenSample, pvBuffer)


    # sine
    # write each quadrant in a own segment
    # --- sine, 1st quarter
    dwSegmentLenSample = dwFactor * 128
    for i in range (0, dwSegmentLenSample, 1):
        for ch in range (0, lNumActiveChannels.value, 1):
            pnData[i * lNumActiveChannels.value + ch] = int16 (dwFShalf.value + int(dwFShalf.value * math.sin (2.0 * math.pi * (i + 0*dwSegmentLenSample) / (dwSegmentLenSample * 4)) + 0.5))
    vWriteSegmentData (hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q1SIN, dwSegmentLenSample, pvBuffer)

    # --- sine, 2nd quarter
    dwSegmentLenSample = dwFactor * 128
    for i in range (0, dwSegmentLenSample, 1):
        for ch in range (0, lNumActiveChannels.value, 1):
            pnData[i * lNumActiveChannels.value + ch] = int16 (dwFShalf.value + int(dwFShalf.value * math.sin (2.0 * math.pi * (i + 1*dwSegmentLenSample) / (dwSegmentLenSample * 4)) + 0.5))
    vWriteSegmentData (hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q2SIN, dwSegmentLenSample, pvBuffer)

    # --- sine, 3rd quarter
    dwSegmentLenSample = dwFactor * 128
    for i in range (0, dwSegmentLenSample, 1):
        for ch in range (0, lNumActiveChannels.value, 1):
            pnData[i * lNumActiveChannels.value + ch] = int16 (dwFShalf.value + int(dwFShalf.value * math.sin (2.0 * math.pi * (i + 2*dwSegmentLenSample) / (dwSegmentLenSample * 4)) + 0.5))
    vWriteSegmentData (hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q3SIN, dwSegmentLenSample, pvBuffer)

    # --- sine, 4th quarter
    dwSegmentLenSample = dwFactor * 128
    for i in range (0, dwSegmentLenSample, 1):
        for ch in range (0, lNumActiveChannels.value, 1):
            pnData[i * lNumActiveChannels.value + ch] = int16 (dwFShalf.value + int(dwFShalf.value * math.sin (2.0 * math.pi * (i + 3*dwSegmentLenSample) / (dwSegmentLenSample * 4)) + 0.5))
    vWriteSegmentData (hCard, lNumActiveChannels, SEGMENT_IDX.SEG_Q4SIN, dwSegmentLenSample, pvBuffer)


    # --- DC level
    dwSegmentLenSample = dwFactor * 128
    for i in range (0, dwSegmentLenSample, 1):
        for ch in range (0, lNumActiveChannels.value, 1):
            pnData[i * lNumActiveChannels.value + ch] = int16 (dwFS.value // 2)

    vWriteSegmentData (hCard, lNumActiveChannels, SEGMENT_IDX.SEG_STOP, dwSegmentLenSample, pvBuffer)


#
#**************************************************************************
# vWriteStepEntry
#**************************************************************************
#

def vWriteStepEntry (hCard, dwStepIndex, dwStepNextIndex, dwSegmentIndex, dwLoops, dwFlags):
    qwSequenceEntry = uint64 (0)

    # setup register value
    qwSequenceEntry = (dwFlags & ~SPCSEQ_LOOPMASK) | (dwLoops & SPCSEQ_LOOPMASK)
    qwSequenceEntry <<= 32
    qwSequenceEntry |= ((dwStepNextIndex << 16)& SPCSEQ_NEXTSTEPMASK) | (int(dwSegmentIndex) & SPCSEQ_SEGMENTMASK)

    dwError = spcm_dwSetParam_i64 (hCard, SPC_SEQMODE_STEPMEM0 + dwStepIndex, int64(qwSequenceEntry))



#
#**************************************************************************
# vConfigureSequence
#**************************************************************************
#

def vConfigureSequence (hCard):
    # sequence memory
    # four sequence loops are programmed (each with 6 steps)
    # a keystroke or ext. trigger switched to the next sequence
    # the loop value for the ramp increase in each sequence
    #  0 ...  5: sync, Q1sin, Q2sin, Q3sin, Q4sin, ramp up
    #  8 ... 13: sync, Q2sin, Q3sin, Q4sin, Q1sin, ramp down
    # 16 ... 21: sync, Q3sin, Q4sin, Q1sin, Q2sin, ramp up
    # 24 ... 29: sync, Q4sin, Q1sin, Q2sin, Q3sin, ramp down

                          #  +-- StepIndex
                          #  |   +-- StepNextIndex
                          #  |   |  +-- SegmentIndex
                          #  |   |  |                          +-- Loops
                          #  |   |  |                          |   +-- Flags: SPCSEQ_ENDLOOPONTRIG
    #  sine               #  |   |  |                          |   |          For using this flag disable Software-Trigger above.
    vWriteStepEntry (hCard,  0,  1, SEGMENT_IDX.SEG_SYNC,      3,  0)
    vWriteStepEntry (hCard,  1,  2, SEGMENT_IDX.SEG_Q1SIN,     1,  0)
    vWriteStepEntry (hCard,  2,  3, SEGMENT_IDX.SEG_Q2SIN,     1,  0)
    vWriteStepEntry (hCard,  3,  4, SEGMENT_IDX.SEG_Q3SIN,     1,  0)
    vWriteStepEntry (hCard,  4,  5, SEGMENT_IDX.SEG_Q4SIN,     1,  0)
    if USING_EXTERNAL_TRIGGER == False:
        vWriteStepEntry (hCard,  5,  1,  SEGMENT_IDX.SEG_RAMPDOWN,  1,  0)
    else:
        vWriteStepEntry (hCard,  5,  8,  SEGMENT_IDX.SEG_RAMPDOWN,  1,  SPCSEQ_ENDLOOPONTRIG)
    # all our sequences come in groups of five segments
    global LAST_STEP_OFFSET
    LAST_STEP_OFFSET = 5

    # cosine
    vWriteStepEntry (hCard,  8,  9, SEGMENT_IDX.SEG_SYNC,      3,  0)
    vWriteStepEntry (hCard,  9, 10, SEGMENT_IDX.SEG_Q2SIN,     1,  0)
    vWriteStepEntry (hCard, 10, 11, SEGMENT_IDX.SEG_Q3SIN,     1,  0)
    vWriteStepEntry (hCard, 11, 12, SEGMENT_IDX.SEG_Q4SIN,     1,  0)
    vWriteStepEntry (hCard, 12, 13, SEGMENT_IDX.SEG_Q1SIN,     1,  0)
    if USING_EXTERNAL_TRIGGER == False:
        vWriteStepEntry (hCard, 13,  9,  SEGMENT_IDX.SEG_RAMPUP,    2,  0)
    else:
        vWriteStepEntry (hCard, 13, 16,  SEGMENT_IDX.SEG_RAMPUP,    2,  SPCSEQ_ENDLOOPONTRIG)

    # inverted sine
    vWriteStepEntry (hCard, 16, 17, SEGMENT_IDX.SEG_SYNC,      3,  0)
    vWriteStepEntry (hCard, 17, 18, SEGMENT_IDX.SEG_Q3SIN,     1,  0)
    vWriteStepEntry (hCard, 18, 19, SEGMENT_IDX.SEG_Q4SIN,     1,  0)
    vWriteStepEntry (hCard, 19, 20, SEGMENT_IDX.SEG_Q1SIN,     1,  0)
    vWriteStepEntry (hCard, 20, 21, SEGMENT_IDX.SEG_Q2SIN,     1,  0)
    if USING_EXTERNAL_TRIGGER == False:
        vWriteStepEntry (hCard, 21, 17,  SEGMENT_IDX.SEG_RAMPDOWN,  3,  0)
    else:
        vWriteStepEntry (hCard, 21, 24,  SEGMENT_IDX.SEG_RAMPDOWN,  3,  SPCSEQ_ENDLOOPONTRIG)

    # inverted cosine
    vWriteStepEntry (hCard, 24, 25, SEGMENT_IDX.SEG_SYNC,      3,  0)
    vWriteStepEntry (hCard, 25, 26, SEGMENT_IDX.SEG_Q4SIN,     1,  0)
    vWriteStepEntry (hCard, 26, 27, SEGMENT_IDX.SEG_Q1SIN,     1,  0)
    vWriteStepEntry (hCard, 27, 28, SEGMENT_IDX.SEG_Q2SIN,     1,  0)
    vWriteStepEntry (hCard, 28, 29, SEGMENT_IDX.SEG_Q3SIN,     1,  0)
    vWriteStepEntry (hCard, 29, 30, SEGMENT_IDX.SEG_RAMPUP,    4,  0)
    vWriteStepEntry (hCard, 30, 30, SEGMENT_IDX.SEG_STOP,      1,  SPCSEQ_END)  # M2i: only a few sample from this segment are replayed
                                                                       # M4i: the complete segment is replayed

    # Configure the beginning (index of first seq-entry to start) of the sequence replay.
    spcm_dwSetParam_i32 (hCard, SPC_SEQMODE_STARTSTEP, 0)

    if False:
        sys.stdout.write ("\n")
        for i in range (0, 32, 1):
            llTemp = int64 (0)
            spcm_dwGetParam_i64 (hCard, SPC_SEQMODE_STEPMEM0 + i, byref (llTemp))
            sys.stdout.write ("Step {0:.2}: 0x{1:016llx}\n".format (i, llTemp))

        sys.stdout.write ("\n\n")


#
# **************************************************************************
# main 
# **************************************************************************
#
# %%
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
    spcm_vClose (hCard)
    exit (1)

# setup the mode
llChEnable = int64 (CHANNEL0)
#llChEnable = int64 (CHANNEL0 | CHANNEL1) # uncomment to enable two channels
lMaxSegments = int32 (32)
spcm_dwSetParam_i32 (hCard, SPC_CARDMODE,            SPC_REP_STD_SEQUENCE)
spcm_dwSetParam_i64 (hCard, SPC_CHENABLE,            llChEnable)
spcm_dwSetParam_i32 (hCard, SPC_SEQMODE_MAXSEGMENTS, lMaxSegments)

# setup trigger
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,      SPC_TMASK_SOFTWARE) # software trigger
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ANDMASK,     0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ORMASK0,  0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ORMASK1,  0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ANDMASK0, 0)
spcm_dwSetParam_i32 (hCard, SPC_TRIG_CH_ANDMASK1, 0)
spcm_dwSetParam_i32 (hCard, SPC_TRIGGEROUT,       0)

# setup the channels
lNumChannels = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_CHCOUNT, byref (lNumChannels))
for lChannel in range (0, lNumChannels.value, 1):
    spcm_dwSetParam_i32 (hCard, SPC_ENABLEOUT0    + lChannel * (SPC_ENABLEOUT1    - SPC_ENABLEOUT0),    1)
    spcm_dwSetParam_i32 (hCard, SPC_AMP0          + lChannel * (SPC_AMP1          - SPC_AMP0),          1000)
    spcm_dwSetParam_i32 (hCard, SPC_CH0_STOPLEVEL + lChannel * (SPC_CH1_STOPLEVEL - SPC_CH0_STOPLEVEL), SPCM_STOPLVL_HOLDLAST)

# set samplerate to 1 MHz (M2i) or 50 MHz, no clock output
spcm_dwSetParam_i32 (hCard, SPC_CLOCKMODE, SPC_CM_INTPLL)
if ((lCardType.value & TYP_SERIESMASK) == TYP_M4IEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M4XEXPSERIES):
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(50))
else:
    spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, MEGA(1))
spcm_dwSetParam_i32 (hCard, SPC_CLOCKOUT,   0)

# generate the data and transfer it to the card
lMaxADCValue = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_MIINST_MAXADCVALUE, byref (lMaxADCValue))
vDoDataCalculation (lCardType, lNumChannels, int32 (lMaxADCValue.value - 1))
sys.stdout.write ("... data has been transferred to board memory\n")

# define the sequence in which the segments will be replayed
vConfigureSequence (hCard)
sys.stdout.write ("... sequence configured\n")

# We'll start and wait until all sequences are replayed.
spcm_dwSetParam_i32 (hCard, SPC_TIMEOUT, 0)
sys.stdout.write ("\nStarting the card\n")
dwErr = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER)
if dwErr != ERR_OK:
    spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_STOP)
    sys.stdout.write ("... Error: {0:d}\n".format(dwErr))
    exit (1)


sys.stdout.write ("\nsequence replay runs, switch to next sequence (3 times possible) with")
if USING_EXTERNAL_TRIGGER == False:
    sys.stdout.write ("\n key: c ... change sequence")
else:
    sys.stdout.write ("\n a (slow) TTL signal on external trigger input connector")
sys.stdout.write ("\n key: ESC ... stop replay and end program\n\n")

lCardStatus = int32 (0)
dwSequenceActual = uint32 (0)    # first step in a sequence
dwSequenceNext = uint32 (0)
lSeqStatusOld = int32 (0)
while True:
    lKey = lKbhit ()
    if lKey == 27: # ESC
        spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_STOP)
        break

    elif lKey == ord ('c') or lKey == ord ('C'):
        if USING_EXTERNAL_TRIGGER == False:
            dwSequenceNext = uint32 ((dwSequenceActual.value + 8) % 32)
            sys.stdout.write ("sequence {0:d}\n".format (dwSequenceNext.value // 8))

            # switch to next sequence
            # (before it is possible to overwrite the segment data of the new used segments with new values)
            llStep = int64 (0)

            # --- change the next step value from the sequence end entry in the actual sequence
            dwErr = spcm_dwGetParam_i64 (hCard, int32 (SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), byref (llStep))
            llStep = int64 ((llStep.value & ~SPCSEQ_NEXTSTEPMASK) | (dwSequenceNext.value << 16))
            dwErr = spcm_dwSetParam_i64 (hCard, int32 (SPC_SEQMODE_STEPMEM0 + dwSequenceActual.value + LAST_STEP_OFFSET), llStep)

            dwSequenceActual = dwSequenceNext
    else:
        sleep(0.01) # 10 ms

        # Demonstrate the two different sequence status values at M2i and M4i / M2p cards.
        lSeqStatus = int32 (0)
        spcm_dwGetParam_i32 (hCard, SPC_SEQMODE_STATUS, byref (lSeqStatus))

        # print the status only when using external trigger to switch sequences
        if USING_EXTERNAL_TRIGGER:
            if lSeqStatusOld != lSeqStatus:
                s_lSeqStatusOld = lSeqStatus

                if ((lCardType.value & TYP_SERIESMASK) == TYP_M2ISERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M2IEXPSERIES): # M2i, M2i-exp
                    if lSeqStatus & SEQSTAT_STEPCHANGE:
                        sys.stdout.write ("status: sequence changed\n")
                if ((lCardType.value & TYP_SERIESMASK) == TYP_M4IEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M4XEXPSERIES) or ((lCardType.value & TYP_SERIESMASK) == TYP_M2PEXPSERIES): # M4i, M4x, M2p
                    # Valid values only at a startet card available.
                    if lCardStatus & M2STAT_CARD_PRETRIGGER:
                        sys.stdout.write ("status: actual sequence number: {0:d}\n".format (lSeqStatus.value))

    # end loop if card reports "ready" state, meaning that it has reached the end of the sequence
    spcm_dwGetParam_i32 (hCard, SPC_M2STATUS, byref (lCardStatus))
    if (lCardStatus.value & M2STAT_CARD_READY) != 0:
        break

# clean up
spcm_vClose (hCard)

