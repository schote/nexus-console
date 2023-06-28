"""Implementation of receive card."""
from dataclasses import dataclass

import numpy as np
from console.spcm_control.device_interface import SpectrumDevice
from console.spcm_control.spcm.pyspcm import *
from console.spcm_control.spcm.spcm_tools import *


@dataclass
class RxCard(SpectrumDevice):
    """Implementation of TX device."""
    
    path: str
    
    __name__: str = "RxCard"
    
    def __post_init__(self):
        super().__init__(self.path)
    
    def setup_card(self):
        pass
    
    def operate(self):
        pass
    
    def get_status(self):
        pass