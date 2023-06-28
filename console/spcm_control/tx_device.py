"""Implementation of transmit card."""
import ctypes
from dataclasses import dataclass

import numpy as np
from console.spcm_control.device_interface import SpectrumDevice
from console.spcm_control.spcm.pyspcm import *
from console.spcm_control.spcm.spcm_tools import *

@dataclass
class TxCard(SpectrumDevice):
    """Implementation of TX device."""
    
    path: str
    channel_enable: list[int]
    max_amplitude: list[int]
    filter_type: list[int]
    sample_rate: int
    
    __name__: str = "TxCard"
    
    def __post_init__(self):
        super().__init__(self.path)
    
    def setup_card(self):
        
        # Reset card
        spcm_dwSetParam_i64 (self.card, SPC_M2CMD, M2CMD_CARD_RESET)
        
        # Set trigger
        spcm_dwSetParam_i32 (self.card, SPC_TRIG_ORMASK, SPC_TM_NONE)
        
        # Set clock mode
        spcm_dwSetParam_i32 (self.card, SPC_CLOCKMODE, SPC_CM_INTPLL)
        spcm_dwSetParam_i64 (self.card, SPC_SAMPLERATE, MEGA(self.sample_rate)) # set card sampling rate in MHz
        
        # Check actual sampling rate
        sample_rate = int64 (0)
        spcm_dwGetParam_i64 (self.card, SPC_SAMPLERATE, byref(sample_rate))
        print(f"Device sampling rate: {sample_rate.value*1e-6} MHz")
        if sample_rate.value != MEGA(self.sample_rate):
            raise Warning(f"Device sample rate {sample_rate.value*1e-6} MHz does not match set sample rate of {self.sample_rate} MHz...")

        # Multi purpose I/O lines
        # spcm_dwSetParam_i32 (self.card, SPCM_X0_MODE, SPCM_XMODE_TRIGOUT) # X0 as gate signal, SPCM_XMODE_ASYNCOUT?
        # spcm_dwSetParam_i32 (self.card, SPCM_X1_MODE, SPCM_XMODE_DISABLE)
        # spcm_dwSetParam_i32 (self.card, SPCM_X2_MODE, SPCM_XMODE_DISABLE)
        # spcm_dwSetParam_i32 (self.card, SPCM_X3_MODE, SPCM_XMODE_DISABLE)
        
        
        # Enable and setup channels
        spcm_dwSetParam_i32 (self.card, SPC_CHENABLE, CHANNEL0 | CHANNEL1 | CHANNEL2 | CHANNEL3)
        
        # Get the number of active channels
        num_channels = int32 (0)
        spcm_dwGetParam_i32(self.card, SPC_CHCOUNT, byref(num_channels))
        print(f"Number of active channels: {num_channels.value}")
        
        # Use loop to enable and setup active channels
        # Channel 0: RF
        spcm_dwSetParam_i32 (self.card, SPC_ENABLEOUT0, self.channel_enable[0])
        spcm_dwSetParam_i32 (self.card, SPC_AMP0, self.max_amplitude[0])
        spcm_dwSetParam_i32 (self.card, SPC_FILTER0, self.filter_type[0])

        # Channel 1: Gradient x
        spcm_dwSetParam_i32 (self.card, SPC_ENABLEOUT0, self.channel_enable[1])
        spcm_dwSetParam_i32 (self.card, SPC_AMP0, self.max_amplitude[1])
        spcm_dwSetParam_i32 (self.card, SPC_FILTER0, self.filter_type[1])
        
        # Channel 2: Gradient y
        spcm_dwSetParam_i32 (self.card, SPC_ENABLEOUT0, self.channel_enable[2])
        spcm_dwSetParam_i32 (self.card, SPC_AMP0, self.max_amplitude[2])
        spcm_dwSetParam_i32 (self.card, SPC_FILTER0, self.filter_type[2])
        
        # Channel 3: Gradient z
        spcm_dwSetParam_i32 (self.card, SPC_ENABLEOUT0, self.channel_enable[3])
        spcm_dwSetParam_i32 (self.card, SPC_AMP0, self.max_amplitude[3])
        spcm_dwSetParam_i32 (self.card, SPC_FILTER0, self.filter_type[3])

        # Setup the card mode
        # FIFO mode
        # spcm_dwSetParam_i32 (self.card, SPC_CARDMODE, SPC_REP_FIFO_SINGLE)
        # spcm_dwSetParam_i64 (self.card, SPC_LOOPS, 0) # continuous replay
        
        # Standard mode
        spcm_dwSetParam_i32 (self.card, SPC_CARDMODE, SPC_REP_STD_SINGLE)
        spcm_dwSetParam_i64 (self.card, SPC_LOOPS, 1)
        
        
    def operate(self, data: np.ndarray):
        
        # *** Thread testing:
        # print("Operating TX Card...")
        # print(f"Sequence data in thread: {data}")
        # self.progress = 0.
        # for k, _ in enumerate(data):
        #     self.progress = round((k+1)/len(data), 2)
        #     if k == int(len(data)/2):
        #         print("Thrd: Half of sequence data processed...")
        #     time.sleep(0.2)
        # return
        
        if data.dtype != np.int16:
            raise ValueError("Invalid type, require data to be int16.")
        
        # For standard mode:
        samples_per_channel = int(len(data)/4)  # Correct?
        spcm_dwSetParam_i32(self.card, SPC_MEMSIZE, samples_per_channel)
        
        # Get pointer to data
        buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        buffer_size = uint64(data.nbytes)
        
        print("Transfer samples to buffer...")
        # Transfer first <notify-size> chunk of data to DMA
        # spcm_dwDefTransfer_i64 defines the transfer buffer by 2 x 32 bit unsigned integer
        # Function arguments: device, buffer type, direction, notify size, pointer to the data buffer, offset - 0 in FIFO mode, transfer length
        spcm_dwDefTransfer_i64 (self.card, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32(0), buffer,  uint64(0), buffer_size)
        
        
        # STANDARD MODE
        # Transfer data, read error, start replay and again read error
        # err = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        # self.handle_error(err)
        # print("Trigger card...")
        # err = spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_FORCETRIGGER | M2CMD_CARD_WAITREADY)
        # self.handle_error(err)
        
        
        # FIFO MODE
        spcm_dwSetParam_i32(self.card, SPC_DATA_AVAIL_CARD_LEN, buffer_size)
        err = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        self.handle_error(err)
        err = spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_FORCETRIGGER | M2CMD_CARD_WAITREADY)
        self.handle_error(err)
        
        
    def get_status(self):
        pass