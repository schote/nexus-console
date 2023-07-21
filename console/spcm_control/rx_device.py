"""Implementation of receive card."""
from dataclasses import dataclass
import ctypes
import numpy as np
import threading
import time

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

    def operate(self, data: np.ndarray):
        event = threading.Event()
        worker = threading.Thread(target=self._fifo_example, args=(data, event))
        worker.start()
        
        # Join after timeout of 10 seconds
        worker.join(10)
        event.set()
        worker.join()
        print("\nThread closed, stopping receiver card...")
        print(data)

    def _receiver_example(self, data: np.ndarray):
        rx_buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        spcm_dwSetParam_i32 (self.card, SPC_MEMSIZE, int(len(rx_buffer)))

        # Read memory size
        memory_size = int64(0)
        spcm_dwGetParam_i32 (self.card, SPC_MEMSIZE, byref(memory_size))
        print(f"Rx device memory size: {memory_size}")

        # Read post trigger
        post_trigger = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        
        spcm_dwGetParam_i32 (self.card, SPC_POSTTRIGGER, byref(post_trigger))
        print(f"Post trigger time: {post_trigger}")   #todo calculate and write time units 
        
        # Trigger delay
        trigger_delay = int64(0)
        spcm_dwGetParam_i32 (self.card, SPC_TRIG_DELAY, byref(trigger_delay))
        print(f"Trigger delay is: {trigger_delay}")   #todo calculate and write time units 

        # X0_mode 
        x0_mode = int64(0)
        spcm_dwGetParam_i32 (self.card, SPCM_X0_MODE, byref(x0_mode))
        print(f"Trigger delay is: {x0_mode}")   #todo calculate and write time units 
        
        #Card start
        err = spcm_dwSetParam_i32(
            self.card,
            SPC_M2CMD,
            M2CMD_CARD_START 
        )
        self.handle_error(err)
        print("Card Started...")
        
        #Enable trigger
        spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_ENABLETRIGGER)
        print("Waiting for trigger...")

        #Set timeout for trigger
        spcm_dwSetParam_i32 (self.card, SPC_TIMEOUT, 10000) #Todo: trigger timeout set to 10 seconds. Maybe make it variable?
        if (spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_WAITTRIGGER) == ERR_TIMEOUT):
        
            print("No trigger detected!! Then, trigger is forced now!..")
            spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_FORCETRIGGER)
       
        spcm_dwSetParam_i32 (self.card, SPC_TIMEOUT, 0)
        spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_WAITREADY)
        
        print ("Card is stopped now...")
        #Transfer the data
        print("Transfer samples from buffer...")
        spcm_dwDefTransfer_i64 (self.card, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, 0, byref(memory_size), 0, memory_size)
        err =spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        self.handle_error(err)
        
    
    def get_status(self):
        pass
