import time
from pydantic import BaseModel, Extra
import numpy as np

from console.spcm_control.pyspcm import *
from console.spcm_control.spcm_tools import *



class SpectrumDevice(BaseModel):
    
    path: str
    card: str = None
    name: str = None
    func_type: int = None
    serial_number: int = None
    card_started: bool = False
    
    class Config:
        # Configuration of pydantic model
        extra = Extra.ignore
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def disconnect(self):
        # Destructor closing the card
        if self.card:
            print(f"Closing spectrum card {self.name}...")
            spcm_vClose(self.card)
            
    def connect(self):
        # Open card
        self.card = spcm_hOpen(create_string_buffer(str.encode(self.path)))
        
        if self.card:
            # read values from card
            card_type = int32(0)
            spcm_dwGetParam_i32(self.card, SPC_PCITYP, byref(card_type))
            serial_number = int32(0)
            spcm_dwGetParam_i32(self.card, SPC_PCISERIALNO, byref(serial_number))
            func_type = int32(0)
            spcm_dwGetParam_i32(self.card, SPC_FNCTYPE, byref(func_type))

            # write values to settings
            self.name = szTypeToName(card_type.value)
            self.serial_number = serial_number
            self.func_type = func_type
            
            self.setup_card()
        else:
            raise ConnectionError("Could not connect to card...")
        
    def handle_error(self, err = None):
        if err:
            # Read and print the error
            err_msg = create_string_buffer(ERRORTEXTLEN)
            spcm_dwGetErrorInfo_i32(self.card, None, None, err_msg)
            print(err_msg)
            # Stop card if started
            if self.card_started:
                spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_STOP)
            # Disconnect
            self.disconnect()
        
    def get_status(self):
        pass
        
    def setup_card(self):
        pass
    
    def operate(self):
        pass
        


class TxCard(SpectrumDevice):
    __name__ = "TxCard"
    
    amplitude: int
    sample_rate: int # in MHz
    buffer_size_samples: int
    progress: int = 0.
    
    # TODO: Define notify and buffer size in config file?
    # notify_size_samples: int
    
    
    def setup_card(self):
        
        # Reset card
        spcm_dwSetParam_i64 (self.card, SPC_M2CMD, M2CMD_CARD_RESET)
        
        # TODO: Check if card is correct card...
        
        # Setup the card mode
        spcm_dwSetParam_i32 (self.card, SPC_CARDMODE, SPC_REP_FIFO_SINGLE) # Configure fifo mode
        # spcm_dwSetParam_i64 (self.card, SPC_SEGMENTSIZE, 0) # used to limit amount of replayed data if SPC_LOOPS != 0 
        # spcm_dwSetParam_i64 (self.card, SPC_LOOPS, 0) # continuous replay
        spcm_dwSetParam_i32 (self.card, SPC_CLOCKOUT, 1) # enable clock output
        spcm_dwSetParam_i64 (self.card, SPC_SAMPLERATE, MEGA(self.sample_rate)) # set card sampling rate in MHz
        
        # Multi purpose I/O lines
        spcm_dwSetParam_i32 (self.card, SPCM_X0_MODE, SPCM_XMODE_TRIGOUT) # X0 as gate signal, SPCM_XMODE_ASYNCOUT?
        spcm_dwSetParam_i32 (self.card, SPCM_X1_MODE, SPCM_XMODE_DISABLE)
        spcm_dwSetParam_i32 (self.card, SPCM_X2_MODE, SPCM_XMODE_DISABLE)
        spcm_dwSetParam_i32 (self.card, SPCM_X3_MODE, SPCM_XMODE_DISABLE)
        
        # Enable and setup channels
        spcm_dwSetParam_i32 (self.card, SPC_CHENABLE, CHANNEL0 | CHANNEL1 | CHANNEL2 | CHANNEL3)
        
        # Get the number of active channels
        num_channels = int32 (0)
        spcm_dwGetParam_i32(self.card, SPC_CHCOUNT, byref(num_channels))
        print(f"Number of active channels: {num_channels.value}")
        
        # Use loop to enable and setup active channels
        for k in range(num_channels.value):
            spcm_dwSetParam_i32 (self.card, SPC_ENABLEOUT0 + k * (SPC_ENABLEOUT1 - SPC_ENABLEOUT0), 1)
            spcm_dwSetParam_i32 (self.card, SPC_AMP0 + k * (SPC_AMP1 - SPC_AMP0), self.amplitude)
            spcm_dwSetParam_i32 (self.card, SPC_FILTER0 + k * (SPC_FILTER1 - SPC_FILTER0), 0)

        # Software trigger
        spcm_dwSetParam_i32 (self.card, SPC_TRIG_ORMASK, SPC_TMASK_SOFTWARE)
        
        # Update actual sampling rate
        sample_rate = int64 (0)
        spcm_dwGetParam_i64 (self.card, SPC_SAMPLERATE, byref(sample_rate))
        
        if sample_rate != self.sample_rate:
            print(f"Driver adjusted the sampling rate, sampling rate now is {sample_rate.value}...")
            self.sample_rate = int(sample_rate.value)
        
    def operate(self, data: np.array):
        
        print("Operating TX Card...")
        print(f"Sequence data in thread: {data}")
        self.progress = 0.
        
        for k, _ in enumerate(data):
            self.progress = round((k+1)/len(data), 2)
            if k == int(len(data)/2):
                print("Thrd: Half of sequence data processed...")
            time.sleep(0.2)
        return
        
        # CHECKS (to be implemented)
        # check size of data - is continuous buffer required?
        
        # Get bytes per sample
        bytes_per_sample = int32 (0)
        spcm_dwGetParam_i32(self.card, SPC_MIINST_BYTESPERSAMPLE, byref(bytes_per_sample))
        print(f"Bytes per sample: {bytes_per_sample.value}")
        
        # Define notify and buffer size in python simple_rep_fifo example:
        notify_size = int32(0)  # int32(128*1024)
        # buffer_size = uint64(32*1024*1024)
        num_samples = len(data)
        buffer_size = uint64(num_samples*4*bytes_per_sample.value)
        # Define pointer to buffer
        # buffer = c_void_p()
        data = np.int16(data)
        buffer = data.ctypes.data_as(ptr16)

        # Transfer first <notify-size> chunk of data to DMA
        # spcm_dwDefTransfer_i64 defines the transfer buffer by 2 x 32 bit unsigned integer
        # Function arguments: device, buffer type, direction, notify size, pointer to the data buffer, offset - 0 in FIFO mode, transfer length
        spcm_dwDefTransfer_i64 (self.card, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, notify_size, buffer, uint64(0), buffer_size)
        
        # Start dma transfer and wait until finished
        self.handle_error(
            spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        )
            
        if not self.card_started:
            self.handle_error(
                spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER)
            )
            self.card_started = True
            
        
        
        
        
class RxCard(SpectrumDevice):
    __name__ = "RxCard"
    
    def setup_card(self):
        pass
    
    def operate(self):
        pass