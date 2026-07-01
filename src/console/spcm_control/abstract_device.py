"""Device interface class."""
import json
from abc import ABC, abstractmethod
from ctypes import _SimpleCData, byref, c_char_p, create_string_buffer
from logging import Logger

import console.spcm_control.spcm.pyspcm as sp
from console.spcm_control.spcm.tools import translate_error, translate_status, type_to_name


class SpectrumDevice(ABC):
    """Spectrum device abstract base class."""

    card: c_char_p | None
    card_type: sp.int32
    name: str | None
    path: str
    log: Logger

    def __init__(self, path: str, log: Logger) -> None:
        """Init function of spectrum device.

        Parameters
        ----------
        path
            Path of the spectrum card device, e.g. /dev/spcm1
        """
        super().__init__()
        self.card = None
        self.card_type = sp.int32(0)
        self.name = None
        self.path = path
        self.log = log

    def dict(self) -> dict:
        """Abstract method which returns variables for logging in dictionary."""
        attributes = {}
        for key, var in vars(self).items():
            # Check if var exists, is not None and its variable name
            # does not have a leading or ending double underscore
            if not key.startswith("__") and not key.endswith("__"):
                if not var or var is None:
                    continue
                if isinstance(var, _SimpleCData):
                    # Is a ctypes type
                    attributes[key] = var.value
                try:
                    # Check if variable can be json serialized
                    json.dumps(var)
                except TypeError:
                    continue
                attributes[key] = var
        return attributes

    def disconnect(self) -> None:
        """Disconnect card."""
        # Closing the card
        if self.card:
            self.log.info(f"Stopping and closing card {self.name}...")
            sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_CARD_STOP)
            sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_CARD_RESET)
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

        # Only connect, if card is not already defined
        self.card = sp.spcm_hOpen(create_string_buffer(str.encode(self.path)))
        if self.card:
            # Read card information
            sp.spcm_dwGetParam_i32(self.card, sp.SPC_PCITYP, byref(self.card_type))
            self.name = type_to_name(self.card_type.value)
            self.log.debug(f"Connection to card {self.name} established!")
            self.setup_card()
        else:
            self.log.critical("Could not connect to card")
            raise ConnectionError("Could not connect to card")
        return True

    def handle_error(self, error: int) -> None:
        """General error handling function."""
        if error != sp.ERR_OK:
            # sp.ERR_OK = 0, this corresponds to "if error:"
            if error == sp.ERR_TIMEOUT:
                # Check for timeout, could be logged but occurs in normal operation
                # self.log.debug("Received timeout")
                return
            # Read error message from card
            err_msg = create_string_buffer(sp.ERRORTEXTLEN)
            if (sp.spcm_dwGetErrorInfo_i32(self.card, None, None, err_msg) != sp.ERR_OK):
                # double check if error is not ERR_OK, disconnect and raise error
                self.log.critical(
                    f"Caught error ( {error} ): {err_msg}, {translate_error(error)}; Stopping card {self.name}"
                )
                sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_CARD_STOP)
                raise RuntimeError

    def get_status(self) -> int:
        """Get and log current card status.

        The status is represented by a list. Each entry represents a possible card status in form
        of a (sub-)list. It contains the status code, name and (optional) description of the spectrum
        instrumentation manual.

        Returns
        -------
            String with status description.
        """
        try:
            status = sp.int32(0)
            sp.spcm_dwGetParam_i32(self.card, sp.SPC_M2STATUS, byref(status))
            if self.log:
                msg, _ = translate_status(status.value, include_desc=False)
                self.log.debug("Card status:\n%s", {key: val for val, key in msg.values()})
        except Exception:
            self.log.exception("Error getting card status.")
        return status.value

    @abstractmethod
    def setup_card(self) -> None:
        """Abstract method to setup the card."""

    @abstractmethod
    def start_operation(self) -> None:
        """Abstract method to start card operation."""

    @abstractmethod
    def stop_operation(self) -> None:
        """Abstract method to stop card operation."""
