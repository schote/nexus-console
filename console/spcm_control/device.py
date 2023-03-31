from pydantic import BaseModel
import yaml

from console.spcm_control.pyspcm import *
from console.spcm_control.spcm_tools import *

# Add constructors to PyYAML loader
yaml_loader = yaml.SafeLoader
yaml_loader.add_constructor("!TxCard", lambda loader, node: TxCard(**loader.construct_mapping(node)))
yaml_loader.add_constructor("!RxCard", lambda loader, node: RxCard(**loader.construct_mapping(node)))

class SpectrumDevice(BaseModel):
    
    path: str
    card: str = None
    name: str = None
    func_type: int = None
    serial_number: int = None
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # open card
        self.card = spcm_hOpen(create_string_buffer(str.encode(self.path)))
        
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
    
    def init_card(self):
        pass


class TxCard(SpectrumDevice):
    __name__ = "TxCard"
    
    amplitude: int
    segment_size: int
    sample_rate: int # in MHz
    
    
    def init_card(self):
        
        # Reset card
        spcm_dwSetParam_i64 (self.card, SPC_M2CMD, M2CMD_CARD_RESET)
        
        # Setup the card mode
        spcm_dwSetParam_i32 (self.card, SPC_CARDMODE, SPC_REP_FIFO_SINGLE) # Configure fifo mode
        spcm_dwSetParam_i64 (self.card, SPC_SEGMENTSIZE, self.segment_size) # used to limit amount of replayed data if SPC_LOOPS != 0 
        spcm_dwSetParam_i64 (self.card, SPC_LOOPS, 0) # continuous replay
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
            self.sample_rate = sample_rate

        # Get bytes per sample
        bytes_per_sample = int32 (0)
        spcm_dwGetParam_i32(self.card, SPC_MIINST_BYTESPERSAMPLE, byref(bytes_per_sample.value))
        print(f"Bytes per sample: {bytes_per_sample}")
        
        
class RxCard(SpectrumDevice):
    __name__ = "RxCard"
    
    def init_card(self):
        pass