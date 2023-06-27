import time
from pydantic import BaseModel, Extra
import numpy as np

from console.spcm_control.pyspcm import *
from console.spcm_control.spcm_tools import *
import ctypes


class SpectrumDevice(BaseModel):
    # TODO: Define as dataclass?
    path: str
    card: str | None = None
    name: str | None = None
    
    class Config:
        # Configuration of pydantic model
        extra = Extra.ignore
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def disconnect(self):
        # Closing the card
        if self.card:
            print(f"Stopping and closing card {self.name}...")
            spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_STOP)
            spcm_vClose(self.card)
            # Reset card information
            self.card = None
            self.name = None
            
    def connect(self):
        # Open card
        print(f"Connecting to card...")
        if self.card:
            raise ConnectionError(f"Already connected to card")
        else:
            # Only connect, if card is not already defined
            self.card = spcm_hOpen(create_string_buffer(str.encode(self.path)))

        if self.card:
            # Read card information
            card_type = int32(0)
            spcm_dwGetParam_i32(self.card, SPC_PCITYP, byref(card_type))
            # func_type = int32(0)
            # spcm_dwGetParam_i32(self.card, SPC_FNCTYPE, byref(func_type))
            
            # write values to settings
            self.name = szTypeToName(card_type.value)
            
            # Print card values
            print(f"Connection to card {self.name} established!")
            self.setup_card()
        else:
            raise ConnectionError("Could not connect to card...")
    
    def handle_error(self, error):
        if error:
            # Read error message from card
            error_msg = create_string_buffer(ERRORTEXTLEN)
            spcm_dwGetErrorInfo_i32(self.card, None, None, error_msg)
            
            # Disconnect and raise error
            print(f"Stopping card {self.name}...")
            spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_STOP)
            raise Warning(f"Card error: {error_msg.value}")
        
    def get_status(self):
        # TODO: Define as abstract method
        pass
        
    def setup_card(self):
        # TODO: Define as abstract method
        pass
    
    def operate(self):
        # TODO: Define as abstract method
        pass
        

class TxCard(SpectrumDevice):
    __name__ = "TxCard"
    # Card configuration
    channel_enable: list[int]
    max_amplitude: list[int]
    filter_type: list[int]
    sample_rate: int # in MHz
    
    progress: int = 0.

    
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
        
        samples_per_channel = int(len(data)/4)  # Correct?
        spcm_dwSetParam_i32(self.card, SPC_MEMSIZE, samples_per_channel)
        
        # Get pointer to data
        buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        # buffer = data.ctypes.data_as(ptr16)


        print("Transfer samples to buffer...")
        # Transfer first <notify-size> chunk of data to DMA
        # spcm_dwDefTransfer_i64 defines the transfer buffer by 2 x 32 bit unsigned integer
        # Function arguments: device, buffer type, direction, notify size, pointer to the data buffer, offset - 0 in FIFO mode, transfer length
        spcm_dwDefTransfer_i64 (self.card, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32(0), buffer,  uint64(0), uint64(data.nbytes))
        
        # Start dma transfer and wait until finished
        err = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        self.handle_error(err)
                
        # if(err != 0):
        #     spcm_dwGetErrorInfo_i32 (self.card, None, None, self.szErrorTextBuffer)
        #     print("Card 1- ERROR in Segment 1")
        #     sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
        #     spcm_vClose (self.card)
        #     return
        
        print("Trigger card...")
        err = spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_FORCETRIGGER | M2CMD_CARD_WAITREADY)
        self.handle_error(err)
        
        # if(err != 0):   
        #     spcm_dwGetErrorInfo_i32 (self.card, None, None, self.szErrorTextBuffer)
        #     print("Card 1- ERROR in Segment 1")
        #     sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
        #     spcm_vClose (self.card)
        #     return


class RxCard(SpectrumDevice):
    __name__ = "RxCard"
    
    def setup_card(self):
        pass
    
    def operate(self):
        pass