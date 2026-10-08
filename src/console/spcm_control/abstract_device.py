"""Device interface class."""
import json
from abc import ABC, abstractmethod
from ctypes import _SimpleCData, byref, c_char_p, c_int32, create_string_buffer
from logging import Logger

try:
    import spcm_core as spcm
except Exception as exc:  # noqa: BLE001, spcm_core raises a bare Exception if the driver is missing or outdated
    _driver_error: Exception | None = exc
else:
    _driver_error = None


class SpectrumDriverError(ConnectionError):
    """Spectrum driver library is not installed or not supported."""


def type_to_name(card_type: int) -> str:
    """Name translation for card type.

    Parameters
    ----------
    card_type
        Card type code, read from register SPC_PCITYP

    Returns
    -------
        Card name as string
    """
    version = card_type & spcm.TYP_VERSIONMASK
    match card_type & spcm.TYP_SERIESMASK:
        case spcm.TYP_M2ISERIES:
            return f"M2i.{version:04x}"
        case spcm.TYP_M2IEXPSERIES:
            return f"M2i.{version:04x}-Exp"
        case spcm.TYP_M3ISERIES:
            return f"M3i.{version:04x}"
        case spcm.TYP_M3IEXPSERIES:
            return f"M3i.{version:04x}-Exp"
        case spcm.TYP_M4IEXPSERIES:
            return f"M4i.{version:04x}-x8"
        case spcm.TYP_M4XEXPSERIES:
            return f"M4x.{version:04x}-x4"
        case spcm.TYP_M2PEXPSERIES:
            return f"M2p.{version:04x}-x4"
        case spcm.TYP_M5IEXPSERIES:
            return f"M5i.{version:04x}-x16"
        case _:
            return "unknown type"


class SpectrumDevice(ABC):
    """Spectrum device abstract base class."""

    card: c_char_p | None
    card_type: c_int32
    name: str | None
    path: str
    log: Logger

    def __init__(self, path: str, log: Logger) -> None:
        """Init function of spectrum device.

        Parameters
        ----------
        path
            Path of the spectrum card device, e.g. /dev/spcm1
        log
            Logger instance of the spectrum device.
        """
        super().__init__()
        self.card = None
        self.card_type = c_int32(0)
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
            spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_STOP)
            spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_RESET)
            spcm.spcm_vClose(self.card)
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
        if _driver_error is not None:
            raise SpectrumDriverError(str(_driver_error)) from _driver_error
        self.log.debug("Connecting to card")
        if self.card:
            # Raise connection error if card object already exists
            self.log.error("Already connected to card")

        # Only connect, if card is not already defined
        self.card = spcm.spcm_hOpen(create_string_buffer(str.encode(self.path)))
        if self.card:
            # Read card information
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_PCITYP, byref(self.card_type))
            self.name = type_to_name(self.card_type.value)
            self.log.debug(f"Connection to card {self.name} established!")
            self.setup_card()
        else:
            self.log.critical("Could not connect to card")
            raise ConnectionError("Could not connect to card")
        return True

    def handle_error(self, error: int) -> None:
        """General error handling function."""
        if error != spcm.ERR_OK:
            # spcm.ERR_OK = 0, this corresponds to "if error:"
            if error == spcm.ERR_TIMEOUT:
                # Check for timeout, could be logged but occurs in normal operation
                # self.log.debug("Received timeout")
                return
            # Read error message, register and value from driver
            reg, val = spcm.uint32(0), spcm.int32(0)
            err_msg = create_string_buffer(spcm.ERRORTEXTLEN)
            spcm.spcm_dwGetErrorInfo_i32(self.card, byref(reg), byref(val), err_msg)
            msg = f"{err_msg.value.decode(errors='replace')} (error {error}, register {reg.value}, value {val.value})"
            self.log.critical(f"{msg}; Stopping card {self.name}")
            spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_STOP)
            raise RuntimeError(msg)

    def get_status(self) -> int:
        """Get current card status and log the names of all set status flags.

        Returns
        -------
            Status register value, see M2STAT_* constants of spcm_core.
        """
        try:
            status = spcm.int32(0)
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_M2STATUS, byref(status))
            if self.log:
                flags = [
                    name for name, flag in vars(spcm).items()
                    if name.startswith(("M2STAT_CARD", "M2STAT_DATA")) and status.value & flag
                ]
                self.log.debug("Card status: %s", flags)
        except Exception:
            self.log.exception("Error getting card status.")
        return status.value

    @abstractmethod
    def setup_card(self) -> None:
        """Abstract method to setup the card."""

    @abstractmethod
    def start_operation(self) -> None:
        """Abstract method to start card operation.

        Parameters
        ----------
        data, optional
            Replay data in correct spcm format as numpy array, by default None
        """

    @abstractmethod
    def stop_operation(self) -> None:
        """Abstract method to stop card operation."""
