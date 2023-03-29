from pydantic import BaseModel
import yaml

from console.spcm_control.pyspcm import *
from console.spcm_control.spcm_tools import *


class SpectrumDevice(BaseModel):
    
    path: str
    card: str = None
    name: str = None
    serial_number: int = None
    func_type: int = None
    
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.card = spcm_hOpen(create_string_buffer(str.encode(self.path)))
        
        # Read values from card
        card_type, serial_number, func_type = int32(0), int32(0), int32(0)
        spcm_dwGetParam_i32(self.card, SPC_PCITYP, byref(card_type))
        spcm_dwGetParam_i32(self.card, SPC_PCISERIALNO, byref(serial_number))
        spcm_dwGetParam_i32(self.card, SPC_FNCTYPE, byref(func_type))

        self.name = szTypeToName(card_type.value)
        self.serial_number = serial_number
        self.func_type = func_type


# Add constructors to PyYAML loader
yaml_loader = yaml.SafeLoader
yaml_loader.add_constructor("!SpectrumDevice", lambda loader, node: SpectrumDevice(**loader.construct_mapping(node)))
