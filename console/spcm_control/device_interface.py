# import ctypes
# import time
from abc import ABC, abstractmethod

# import numpy as np
from console.spcm_control.spcm.pyspcm import *
from console.spcm_control.spcm.spcm_tools import *
# from pydantic import BaseModel, Extra


class SpectrumDevice(ABC):
    """Spectrum device abstract base class."""
    
    def __init__(self, path: str):
        """Init function of spectrum device.

        Parameters
        ----------
        path
            Path of the spectrum card device, e.g. /dev/spcm1
        """
        super().__init__()
        self.card: str | None = None
        self.name: str | None = None
        self.path = path
    
    def disconnect(self):
        """Disconnect card."""
        # Closing the card
        if self.card:
            print(f"Stopping and closing card {self.name}...")
            spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_STOP)
            spcm_vClose(self.card)
            # Reset card information
            self.card = None
            self.name = None
            
    def connect(self):
        """Establish card connection."""
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
        """General error handling function."""
        if error:
            # Read error message from card
            error_msg = create_string_buffer(ERRORTEXTLEN)
            spcm_dwGetErrorInfo_i32(self.card, None, None, error_msg)
            
            # Disconnect and raise error
            print(f"Stopping card {self.name}...")
            spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_STOP)
            raise Warning(f"Card error: {error_msg.value}")

    @abstractmethod
    def get_status(self):
        """Abstract method to obtain card status."""
        pass

    @abstractmethod
    def setup_card(self):
        """Abstract method to setup the card."""
        pass

    @abstractmethod
    def operate(self):
        """Abstract method to operate the card."""
        pass