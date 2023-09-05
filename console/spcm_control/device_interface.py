"""Device interface class."""
from abc import ABC, abstractmethod

import numpy as np

import console.spcm_control.spcm.pyspcm as spcm
from console.spcm_control.spcm.spcm_tools import translate_error, type_to_name


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
            spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_STOP)
            spcm.spcm_vClose(self.card)
            # Reset card information
            self.card = None
            self.name = None

    def connect(self):
        """Establish card connection.

        Raises
        ------
        ConnectionError
            Connection to card already exists
        ConnectionError
            Connection could not be established
        """
        print("Connecting to card...")
        if self.card:
            # Raise connection error if card object already exists
            raise ConnectionError("Already connected to card")
        # Only connect, if card is not already defined
        self.card = spcm.spcm_hOpen(spcm.create_string_buffer(str.encode(self.path)))
        if self.card:
            # Read card information
            card_type = spcm.int32(0)
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_PCITYP, spcm.byref(card_type))

            # write values to settings
            self.name = type_to_name(card_type.value)

            # Print card values
            print(f"Connection to card {self.name} established!")
            self.setup_card()
        else:
            raise ConnectionError("Could not connect to card...")

    def handle_error(self, error):
        """General error handling function."""
        if error:
            # Read error message from card
            err_msg = spcm.create_string_buffer(spcm.ERRORTEXTLEN)
            spcm.spcm_dwGetErrorInfo_i32(self.card, None, None, err_msg)

            # Disconnect and raise error
            print(f"Catched error:\n{err_msg}\nStopping card {self.name}...")
            spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_STOP)

            raise Warning(translate_error(error))

    @abstractmethod
    def get_status(self):
        """Abstract method to obtain card status."""

    @abstractmethod
    def setup_card(self):
        """Abstract method to setup the card."""

    @abstractmethod
    def start_operation(self, data: np.ndarray | None = None):
        """Abstract method to start card operation.

        Parameters
        ----------
        data, optional
            Replay data in correct spcm format as numpy array, by default None
        """

    @abstractmethod
    def stop_operation(self):
        """Abstract method to stop card operation."""