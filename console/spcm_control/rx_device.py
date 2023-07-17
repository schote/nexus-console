"""Implementation of receive card."""
from dataclasses import dataclass
import ctypes
import numpy as np

from console.spcm_control.device_interface import SpectrumDevice
from console.spcm_control.spcm.pyspcm import *
from console.spcm_control.spcm.spcm_tools import *


@dataclass
class RxCard(SpectrumDevice):
    """Implementation of TX device."""

    path: str
    channel_enable: list[int]
    max_amplitude: list[int]
    __name__: str = "RxCard"

    def __post_init__(self):
        super().__init__(self.path)

    def setup_card(self):
        # Reset card
        spcm_dwSetParam_i64(self.card, SPC_M2CMD, M2CMD_CARD_RESET) #Needed?

        #Setup channels
  
        spcm_dwGetParam_i32(self.card, SPC_CHCOUNT, byref(self.num_channels))
        print(f"Number of active Rx channels: {self.num_channels.value}")

        # and voltage setting for channel0
        spcm_dwSetParam_i32(self.card, SPC_CHENABLE, self.channel_enable[0])
        spcm_dwSetParam_i32(self.card, SPC_50OHM0, 0) #Todo make it variable or input impedance always 50 ohms?  
        spcm_dwSetParam_i32(self.card, SPC_AMP0, self.max_amplitude[0])

        #Input impdefance and voltage setting for channel1
        spcm_dwSetParam_i32(self.card, SPC_CHENABLE, self.channel_enable[1])
        spcm_dwSetParam_i32(self.card, SPC_50OHM1, 0) #Todo make it variable or input impedance always 50 ohms?  
        spcm_dwSetParam_i32(self.card, SPC_AMP1, self.max_amplitude[1])

        #Digital filter setting for receiver
        spcm_dwSetParam_i32 (self.card, SPC_DIGITALBWFILTER, 0)

        # Set clock mode
        spcm_dwSetParam_i32(self.card, SPC_CLOCKMODE, SPC_CM_INTPLL)

        # Output clock is available
        spcm_dwSetParam_i32 (self.card, SPC_CLOCKOUT, 1)

        # Set card sampling rate in MHz
        spcm_dwSetParam_i64(
            self.card, SPC_SAMPLERATE, MEGA(self.sample_rate)
        )
        # Check actual sampling rate
        sample_rate = int64(0)
        spcm_dwGetParam_i64(self.card, SPC_SAMPLERATE, byref(sample_rate))
        print(f"Rx device sampling rate: {sample_rate.value*1e-6} MHz")
        if sample_rate.value != MEGA(self.sample_rate):
            raise Warning(
                f"Rx device sample rate {sample_rate.value*1e-6} MHz does not match set sample rate of {self.sample_rate} MHz..."
            )


        
         # Trigger delay
        trigger_delay = int64(0)
        spcm_dwGetParam_i32 (self.card, SPC_TRIG_DELAY, byref(trigger_delay))
        print(f"Trigger delay is: {trigger_delay}")   #todo calculate and write time units 

        # X0_mode 
        x0_mode = int64(0)
        spcm_dwGetParam_i32 (self.card, SPCM_X0_MODE, byref(x0_mode))
        print(f"Trigger delay is: {x0_mode}")   #todo calculate and write time units 

        #spcm_dwGetParam_i32 (hDrv, SPC_PCITYP, &lCardType);
        #printf ("Found M2p.%04x in the system\n", lCardType & TYP_VERSIONMASK);




        
        # Multi purpose I/O lines
        # spcm_dwSetParam_i32 (self.card, SPCM_X0_MODE, SPCM_XMODE_TRIGOUT) # X0 as gate signal, SPCM_XMODE_ASYNCOUT?
        # spcm_dwSetParam_i32 (self.card, SPCM_X1_MODE, SPCM_XMODE_DISABLE)
        # spcm_dwSetParam_i32 (self.card, SPCM_X2_MODE, SPCM_XMODE_DISABLE)
        # spcm_dwSetParam_i32 (self.card, SPCM_X3_MODE, SPCM_XMODE_DISABLE)



        # Get the number of active channels


        # Setup the card mode


        # FIFO mode
        spcm_dwSetParam_i32 (self.card, SPC_CARDMODE, SPC_REC_STD_SINGLE);
        #spcm_dwSetParam_i32 (self.card, SPC_MEMSIZE, *lMemsize);
        #spcm_dwSetParam_i32 (self.card, SPC_POSTTRIGGER, *posttr);
        #spcm_dwSetParam_i32 (self.card, SPC_LOOPS, 1);

    def operate(self):
        pass

    def _receiver_example(self, data: np.ndarray):
        rx_buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        spcm_dwSetParam_i32 (self.card, SPC_MEMSIZE, rx_buffer)
        
        # Read post trigger
        post_trigger = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        
        spcm_dwGetParam_i32 (self.card, SPC_POSTTRIGGER, byref(post_trigger))
        print(f"Post trigger time: {post_trigger}")   #todo calculate and write time units 

        # Read memory size
        memory_size = int64(0)
        spcm_dwGetParam_i32 (self.card, SPC_MEMSIZE, byref(memory_size))
        print(f"Rx device memory size: {memory_size}")
    def get_status(self):
        pass
