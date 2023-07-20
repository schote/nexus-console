Date: 20.07.2023, 13:00-15:00
Participants: Christoph Kolbitsch (CK) ,David Schote (DS),  Lukas Winter (LW), Frank Seifert (FS), Berk Silemek(BS) , Patrick Schünke (PS), Felix Zimmermann(FZ_

ALL: GPU? Maybe we may add GPU for deep learning stuff
Some missing events for Pulseq: Trigger event, Delay event 

Add to gitlab: Presentatıon and minutes of meeting under the created meeting folder

Sequence unrolling: Enough memory? Overhead for timing?

Fz: What is the purpose of unrolling runtime?
DS: All channels are the same sampling rate and synched. So, gradients and RF are together: Too much memory. 
LW: Maybe we can play out the gradient waveform from OCRA board?
FS: Real time approach is fine but we need to consider latency. 20-30 ms should be possible with optimization in the future. 
Calculating the whole sequence can be a starting point. 
Phase coherence. We have no local oscillator. Adding pulses might be challenging. Phase evolution might be challenging to calculate. 
Receive cards are not synched. Phase pattern can be transmitted from the card and receiver cards can extract the phase. 
Maybe sequence mode?
ALL: How ring buffer is implemented and Is there a way to get rid of the code overhead in Python. 
ALL: Lets continue with the FIFO mode, if we see issues we will report. 

ISSUE with playing out FIFO again after one finishes: 
Suggestion maybe check the buffer position if everything is played out. 

LW: Is unblank signal in the ring buffer?
FS: Unblank can be played out from digital ports by using bit operations.
BS: I will implement trigger for this one.
LW+BS+FS: Digital output is 3.3V, we need to convert it to 5 V.

DS + FS: Filtering for receiver cards? The options 3 MHz , 5 MHz and etc. will be doublechecked.  

LW: Larmor frequency can be changed without restarting the cards? Field probe integration with ADC  cards?
FS + BS: Yes, it can be adjusted runtime. However, sampling rate change may require card restart.

Pulseq 
Internal sequence language translation. 

LW: Digital modulation of the RF pulses. Maybe ask other people?
FS will help DS for the down conversion. 

PS: Samples , gradients with couple of thousand points. .Seq file can be large for a regular Pulseq implementation. It is not an issue.
CK: raster pulseq shape just for definition. 
LW: Do we need to optimize the sequence implementation for a starting point? Maybe we need to change it later, so let's start with a simple working version.  
DS: start with implementation to see how slow is it?

General discussion: What should be the sampling rate?

DS and FS  will discuss in the next week

TSE pulseseq sequence will be tested.
pypulseq implementation? 

CK: Comparing the different pulses , transmit and receive chain. Is it feasible reading large files from oscilloscope to a python script? 
BS: Yes, it is possible; however, we will switch to receiver cards for the reception. BS has not finished the implementation of receiver cards.   

FZ,DS,PS: Reading from seq files or py files?
Seq file is better because we can compare to other systems. 

CK recommends ismrmd format for reconstruction. Maybe it is better to start now for a smooth adaptation. 


Follow-up meeting: 28.08.2023 16:00, Confirmed participants: CK, DS, BS, LW, FZ, PS
