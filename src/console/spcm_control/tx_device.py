"""Implementation of transmit card."""
import ctypes
import logging
import threading
from dataclasses import dataclass

import numpy as np

import console.spcm_control.spcm.pyspcm as spcm
from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from console.spcm_control.abstract_device import SpectrumDevice
from console.spcm_control.spcm.tools import create_dma_buffer, translate_status, type_to_name


@dataclass
class TxCard(SpectrumDevice):
    """
    Implementation of TX device.

    Implements abstract base class SpectrumDevice, which requires the abstract methods get_status(),
    setup_card() and operate(). The TxCard is automatically instantiated by a yaml-loader when
    loading the configuration file.

    The implementation was done and tested with card M2p6546-x4, which has an onboard
    memory size of 512 MSample, 2 Bytes/sample => 1024 MB.

    Overview:
    ---------
    The TX card operates with a ring buffer on the spectrum card, defined by ring_buffer_size.
    The ring buffer is filled in fractions of notify_size.
    """

    path: str
    max_amplitude: list[int]
    filter_type: list[int]
    sample_rate: int
    notify_rate: int = 16

    __name__: str = "TxCard"

    def __post_init__(self):
        """Post init function which is required to use dataclass arguments."""
        self.log = logging.getLogger(self.__name__)
        super().__init__(self.path, log=self.log)

        # Number of output channels is fixed
        self.num_ch = 4
        # Size of the current sequence
        self.data_buffer_size = int(0)
        # Define ring buffer and notify size, 512 MSamples * 2 Bytes = 1024 MB
        self.ring_buffer_size: spcm.uint64 = spcm.uint64(1024**3)
        self.card_type = spcm.int32(0)

        try:
            # Check if ring buffer size is multiple of 2*num_ch (2 bytes per sample per channel)
            if self.ring_buffer_size.value % (self.num_ch * 2) != 0:
                raise MemoryError(
                    "Ring buffer size is not a multiple of channel sample product \
                    (number of enables channels times 2 byte per sample)"
                )
        except MemoryError as err:
            self.log.exception(err, exc_info=True)
            raise err

        if self.ring_buffer_size.value % self.notify_rate == 0:
            self.notify_size = spcm.int32(int(self.ring_buffer_size.value / self.notify_rate))
        else:
            # Set default fraktion to 16, notify size equals 1/16 of ring buffer size
            self.notify_size = spcm.int32(int(self.ring_buffer_size.value / 16))

        self.log.debug("Ring buffer size: %s; Notify size: %s", self.ring_buffer_size.value, self.notify_size.value)

        # Threading class attributes
        self.worker: threading.Thread | None = None
        self.is_running = threading.Event()

    def setup_card(self) -> None:
        """Set up spectrum card in transmit (TX) mode.

        At the very beginning, a card reset is performed. The clock mode is set according to the sample rate,
        defined by the class attribute.
        All 4 channels are enables and configured by max. amplitude and filter values from class attributes.
        Digital outputs X0, X1 and X2 are defined which are controlled by the 15th bit of analog outputs 1, 2 and 3.

        Raises
        ------
        Warning
            The actual set sample rate deviates from the corresponding class attribute to be set,
            class attribute is overwritten.
        """
        # Reset card
        spcm.spcm_dwSetParam_i64(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_RESET)
        spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_PCITYP, ctypes.byref(self.card_type))

        try:
            if "M2p.65" not in (device_type := type_to_name(self.card_type.value)):
                raise ConnectionError(
                    "Device with path %s is of type %s, no transmit card..." % (self.path, device_type)
                )
        except ConnectionError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # >> TODO: At this point, card alread has M2STAT_CARD_PRETRIGGER and M2STAT_CARD_TRIGGER set, correct?

        # Set trigger
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_TRIG_ORMASK, spcm.SPC_TMASK_SOFTWARE)

        # Set clock mode
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_CLOCKMODE, spcm.SPC_CM_INTPLL)
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_CLOCKOUT, 1)

        # set card sampling rate in MHz
        spcm.spcm_dwSetParam_i64(self.card, spcm.SPC_SAMPLERATE, spcm.MEGA(self.sample_rate))

        # Check actual sampling rate
        sample_rate = spcm.int64(0)
        spcm.spcm_dwGetParam_i64(self.card, spcm.SPC_SAMPLERATE, ctypes.byref(sample_rate))
        self.log.info("Device sampling rate: %s MHz", sample_rate.value * 1e-6)
        if sample_rate.value != spcm.MEGA(self.sample_rate):
            self.log.warning(
                "Tx device sample rate %s MHz does not match set sample rate of %s MHz",
                sample_rate.value * 1e-6,
                self.sample_rate,
            )
            self.sample_rate = int(sample_rate.value * 1e-6)

        # Enable and setup channels
        spcm.spcm_dwSetParam_i32(
            self.card, spcm.SPC_CHENABLE, spcm.CHANNEL0 | spcm.CHANNEL1 | spcm.CHANNEL2 | spcm.CHANNEL3
        )

        # Use loop to enable and setup active channels
        # Channel 0: RF
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT0, 1)
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP0, self.max_amplitude[0])
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER0, self.filter_type[0])

        # Channel 1: Gradient x, synchronus digital output: gate trigger
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT1, 1)
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP1, self.max_amplitude[1])
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER1, self.filter_type[1])

        # Channel 2: Gradient y, synchronus digital output: un-blanking
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT2, 1)
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP2, self.max_amplitude[2])
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER2, self.filter_type[2])

        # Channel 3: Gradient z
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT3, 1)
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP3, self.max_amplitude[3])
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER3, self.filter_type[3])

        # Setup the card in FIFO mode
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_CARDMODE, spcm.SPC_REP_FIFO_SINGLE)

        # >> Setup digital output channels
        # Channel X1: digital ADC gate (analog channel 1)
        # Channel X2: digital RF unblanking signal (analog channel 2)
        # Channel X3: digital phase reference (analog channel 3)

        spcm.spcm_dwSetParam_i32(
            self.card,
            spcm.SPCM_X1_MODE,
            (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH1 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
        )
        spcm.spcm_dwSetParam_i32(
            self.card,
            spcm.SPCM_X2_MODE,
            (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH2 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
        )
        spcm.spcm_dwSetParam_i32(
            self.card,
            spcm.SPCM_X3_MODE,
            (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH3 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
        )

        self.log.debug("Device setup completed")
        self.log_card_status()

    def start_operation(self, data: UnrolledSequence | None = None) -> None:
        """Start transmit (TX) card operation.

        Steps:
        (1) Setup the transmit card
        (2) Clear emergency stop flag, reset to False
        (3) Start worker thread (card streaming mode), with provided replay data

        Parameters
        ----------
        data
            Sequence replay data as int16 numpy array in correct order.
            Checkout `prepare_sequence` function for reference of correct replay data format.
            This value is None per default

        Raises
        ------
        ValueError
            Raised if replay data is not provided as numpy int16 values
        """
        try:
            # Data must have a default value as start_operation is an abstract method and data is optional
            if not data:
                raise ValueError("No unrolled sequence data provided.")
            sqnc = np.concatenate(data.seq)

            # Check if sequence datatype is valid
            if sqnc.dtype != np.int16:
                raise ValueError("Sequence replay data is not int16, please unroll sequence to int16.")

            # Check if card connection is established
            if not self.card:
                raise ConnectionError("No connection to card established...")

            # Extend the provided data array with zeros to obtain a multiple of ring buffer size in memory
            if (rest := sqnc.nbytes % self.ring_buffer_size.value) != 0:
                rest = self.ring_buffer_size.value - rest
                if rest % 2 != 0:
                    raise MemoryError("Providet data array size is not a multiple of 2 bytes (size of one sample)")

                fill_size = int((rest) / 2)
                sqnc = np.append(sqnc, np.zeros(fill_size, dtype=np.int16))
                self.log.debug("Appended %s zeros to data array", fill_size)

        except Exception as exc:
            self.log.exception(exc, exc_info=True)
            raise exc

        # Check if sequence dwell time is valid
        if sqnc_sample_rate := 1 / (data.dwell_time * 1e6) != self.sample_rate:
            self.log.warning(
                "Sequence sample rate (%s MHz) differs from device sample rate (%s MHz).",
                sqnc_sample_rate,
                self.sample_rate,
            )

        # Setup card, clear emergency stop thread event and start thread
        self.is_running.clear()
        self.worker = threading.Thread(target=self._fifo_stream_worker, args=(sqnc,))
        self.worker.start()

    def stop_operation(self) -> None:
        """Stop card operation by thread event and stop card."""
        if self.worker is not None:
            self.is_running.set()
            self.worker.join()

            error = spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_STOP | spcm.M2CMD_DATA_STOPDMA)

            self.handle_error(error)
            self.worker = None
        else:
            print("No active replay thread found...")

    def _fifo_stream_worker(self, data: np.ndarray) -> None:
        """Continuous FIFO mode examples.

        Parameters
        ----------
        data
            Numpy array of data to be replayed by card.
            Replay data should be in the format:
            >>> [c0_0, c1_0, c2_0, c3_0, c0_1, c1_1, c2_1, c3_1, ..., cX_N]
            Here, X denotes the channel and the subsequent index N the sample index.
        """
        try:
            # Get total size of data buffer to be played out
            self.data_buffer_size = int(data.nbytes)
            if self.data_buffer_size % (self.num_ch * 2) != 0:
                raise MemoryError(
                    "Replay data size is not a multiple of enabled channels times 2 (bytes per sample)..."
                )
        except MemoryError as err:
            self.log.exception(err, exc_info=True)
            raise err

        self.log.debug("Replay data buffer: %s bytes", self.data_buffer_size)

        # >> Define software buffer
        # Setup replay data buffer
        data_buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        # Allocate continuous ring buffer as defined by class attribute
        ring_buffer = create_dma_buffer(self.ring_buffer_size.value)

        try:
            # Perform initial memory transfer: Fill the whole ring buffer
            if _ring_buffer_pos := ctypes.cast(ring_buffer, ctypes.c_void_p).value:
                if _data_buffer_pos := ctypes.cast(data_buffer, ctypes.c_void_p).value:
                    ctypes.memmove(_ring_buffer_pos, _data_buffer_pos, self.ring_buffer_size.value)
                    transferred_bytes = self.ring_buffer_size.value
                else:
                    raise RuntimeError("Could not get data buffer position")
            else:
                raise RuntimeError("Could not get ring buffer position")
        except RuntimeError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Perform initial data transfer to completely fill continuous buffer
        spcm.spcm_dwDefTransfer_i64(
            self.card,
            spcm.SPCM_BUF_DATA,
            spcm.SPCM_DIR_PCTOCARD,
            self.notify_size,
            ring_buffer,
            spcm.uint64(0),
            self.ring_buffer_size,
        )
        spcm.spcm_dwSetParam_i64(self.card, spcm.SPC_DATA_AVAIL_CARD_LEN, self.ring_buffer_size)

        self.log.debug("Starting card memory transfer")
        error = spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_DATA_STARTDMA | spcm.M2CMD_DATA_WAITDMA)
        self.handle_error(error)

        # Start card
        self.log.debug("Starting card operation")
        error = spcm.spcm_dwSetParam_i32(
            self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_START | spcm.M2CMD_CARD_ENABLETRIGGER
        )
        self.handle_error(error)

        avail_bytes = spcm.int32(0)
        usr_position = spcm.int32(0)
        transfer_count = 0

        while (transferred_bytes < self.data_buffer_size) and not self.is_running.is_set():
            # Read available bytes and user position
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_DATA_AVAIL_USER_LEN, ctypes.byref(avail_bytes))
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_DATA_AVAIL_USER_POS, ctypes.byref(usr_position))

            # Calculate new data for the transfer, when notify_size is available on continous buffer
            if avail_bytes.value >= self.notify_size.value:
                transfer_count += 1

                # Get new buffer positions
                if ring_buffer_position := ctypes.cast(
                    (ctypes.c_char * (self.ring_buffer_size.value - usr_position.value)).from_buffer(
                        ring_buffer, usr_position.value
                    ),
                    ctypes.c_void_p,
                ).value:
                    if current_data_buffer := ctypes.cast(data_buffer, ctypes.c_void_p).value:
                        data_buffer_position = current_data_buffer + transferred_bytes

                        # Move memory: Current ring buffer position,
                        # position in sequence data and amount to transfer (=> notify size)
                        ctypes.memmove(ring_buffer_position, data_buffer_position, self.notify_size.value)

                spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_DATA_AVAIL_CARD_LEN, self.notify_size)
                transferred_bytes += self.notify_size.value

                error = spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_DATA_WAITDMA)
                self.handle_error(error)

        self.log.debug("Card operation stopped")

    def get_status(self) -> int:
        """Get the current card status.

        Returns
        -------
            String with status description.
        """
        try:
            if not self.card:
                raise ConnectionError("No device found")
        except ConnectionError as err:
            self.log.exception(err, exc_info=True)
            raise err
        status = spcm.int32(0)
        spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_M2STATUS, ctypes.byref(status))
        return status.value

    def log_card_status(self, include_desc: bool = False) -> None:
        """Log current card status.

        The status is represented by a list. Each entry represents a possible card status in form
        of a (sub-)list. It contains the status code, name and (optional) description of the spectrum
        instrumentation manual.

        Parameters
        ----------
        include_desc, optional
            Flag which indicates if description string should be contained in status entry, by default False
        """
        msg, _ = translate_status(self.get_status(), include_desc=include_desc)
        status = {key: val for val, key in msg.values()}
        self.log.debug("Card status:\n%s", status)
