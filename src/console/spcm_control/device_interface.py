"""Device interface class."""
from logging import Logger
from abc import ABC, abstractmethod
import warnings
from ctypes import byref, c_char_p, create_string_buffer

import console.spcm_control.spcm.pyspcm as sp
from console.spcm_control.spcm.tools import translate_error, type_to_name


class SpectrumDevice(ABC):
    """Spectrum device abstract base class."""

    def __init__(self, path: str, log: Logger):
        """Init function of spectrum device.

        Parameters
        ----------
        path
            Path of the spectrum card device, e.g. /dev/spcm1
        """
        super().__init__()
        self.card: c_char_p | None = None
        self.name: str | None = None
        self.path = path
        self.log = log

    def disconnect(self):
        """Disconnect card."""
        # Closing the card
        if self.card:
            self.log.info(f"Stopping and closing card {self.name}...")
            sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_CARD_STOP)
            sp.spcm_vClose(self.card)
            # Reset card information
            self.card = None
            self.name = None

    def connect(self) -> bool:
        """Establish card connection.

        Raises
        ------
        ConnectionError
            Connection to card already exists
        ConnectionError
            Connection could not be established
        """
        self.log.debug("Connecting to card")
        if self.card:
            # Raise connection error if card object already exists
            self.log.error("Already connected to card")
            warnings.warn("Already connected to card")
            # raise ConnectionError("Already connected to card")
        # Only connect, if card is not already defined
        self.card = sp.spcm_hOpen(create_string_buffer(str.encode(self.path)))
        if self.card:
            # Read card information
            card_type = sp.int32(0)
            sp.spcm_dwGetParam_i32(self.card, sp.SPC_PCITYP, byref(card_type))
            self.name = type_to_name(card_type.value)
            self.log.debug(f"Connection to card {self.name} established!")
            self.setup_card()
        else:
            self.log.critical("Could not connect to card")
            raise ConnectionError("Could not connect to card")
        return True

    def handle_error(self, error: int):
        """General error handling function."""
        if error:
            # Read error message from card
            err_msg = create_string_buffer(sp.ERRORTEXTLEN)
            sp.spcm_dwGetErrorInfo_i32(self.card, None, None, err_msg)
            
            # Disconnect and raise error
            self.log.critical(f"Catched error: {err_msg}, {translate_error(error)}; stopping card {self.name}")
            sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_CARD_STOP)

    @abstractmethod
    def get_status(self) -> int:
        """Abstract method to obtain card status."""

    @abstractmethod
    def setup_card(self):
        """Abstract method to setup the card."""

    @abstractmethod
    def start_operation(self):
        """Abstract method to start card operation.

        Parameters
        ----------
        data, optional
            Replay data in correct spcm format as numpy array, by default None
        """

    @abstractmethod
    def stop_operation(self):
        """Abstract method to stop card operation."""
