"""Implementation of transmit card."""
import ctypes
import logging
import threading

import numpy as np

import console.spcm_control.spcm.pyspcm as spcm
from console.interfaces.acquisition_parameter import Dimensions
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.spcm_control.abstract_device import SpectrumDevice
from console.spcm_control.spcm.tools import create_dma_buffer, type_to_name

TX_NOTIFY_RATE = 16


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

    __name__: str = "TxCard"

    def __init__(
        self,
        path: str,
        max_amplitude: tuple[int, int, int, int],
        filter_type: tuple[int, int, int, int],
        sample_rate: int,
    ) -> None:
        self.log = logging.getLogger(self.__name__)
        super().__init__(path=path, log=self.log)
        self.max_amplitude = max_amplitude
        self.filter_type = filter_type
        self.sample_rate = sample_rate

        # Number of output channels is fixed
        self.num_ch = 4
        # Size of the current sequence
        self.data_buffer_size: int = 0

        # Define maximum ring buffer size, 512 MSamples * 2 Bytes = 1024 MB
        self.max_ring_buffer_size: spcm.uint64 = spcm.uint64(1024**3)

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
        self.handle_error(spcm.spcm_dwSetParam_i64(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_RESET))
        spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_PCITYP, ctypes.byref(self.card_type))

        try:
            if "M2p.65" not in (device_type := type_to_name(self.card_type.value)):
                raise ConnectionError(
                    "Device with path %s is of type %s, no transmit card..." % (self.path, device_type)
                )
        except ConnectionError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Check for presence of IO expansion cards
        card_features = spcm.int32(0)
        spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_PCIFEATURES, ctypes.byref(card_features))

        # Set trigger
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_TRIG_ORMASK, spcm.SPC_TMASK_SOFTWARE)

        # Configure external clock, TX master clock
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_CLOCKMODE, spcm.SPC_CM_EXTERNAL))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_CLOCK50OHM, 1))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_CLOCK_THRESHOLD, 1500))

        # set card sampling rate in MHz
        self.handle_error(spcm.spcm_dwSetParam_i64(self.card, spcm.SPC_SAMPLERATE, spcm.MEGA(self.sample_rate)))

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
        self.handle_error(spcm.spcm_dwSetParam_i32(
            self.card,
            spcm.SPC_CHENABLE,
            spcm.CHANNEL0 | spcm.CHANNEL1 | spcm.CHANNEL2 | spcm.CHANNEL3,
        ))

        self.log.info("Setup max. output amplitude: %s.", self.max_amplitude)

        # Use loop to enable and setup active channels
        # Channel 0: RF
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT0, 1))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP0, self.max_amplitude[0]))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER0, self.filter_type[0]))

        # Channel 1: Gradient x, synchronus digital output: gate trigger
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT1, 1))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP1, self.max_amplitude[1]))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER1, self.filter_type[1]))

        # Channel 2: Gradient y, synchronus digital output: un-blanking
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT2, 1))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP2, self.max_amplitude[2]))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER2, self.filter_type[2]))

        # Channel 3: Gradient z
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT3, 1))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP3, self.max_amplitude[3]))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER3, self.filter_type[3]))

        # Setup the card in FIFO mode
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_CARDMODE, spcm.SPC_REP_FIFO_SINGLE))

        # >> Setup digital output channels
        # Channel X1: dig. ADC gate (15th bit from analog channel 1)
        self.handle_error(spcm.spcm_dwSetParam_i32(
            self.card,
            spcm.SPCM_X1_MODE,
            (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH1 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
        ))
        # Channel X2: dig. reference signal (15th bit from analog channel 2)
        self.handle_error(spcm.spcm_dwSetParam_i32(
            self.card,
            spcm.SPCM_X2_MODE,
            (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH2 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
        ))
        # Channel X3: dig. unblanking signal (15th bit of analog channel 3)
        self.handle_error(spcm.spcm_dwSetParam_i32(
            self.card,
            spcm.SPCM_X3_MODE,
            (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH3 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
        ))

        # >> Setup additional GPIO ports, if extender is available
        if card_features.value & (spcm.SPCM_FEAT_DIG16_FX2 | spcm.SPCM_FEAT_DIG16_SMB):
            self.log.info("IO expansion card with FX2 connector detected, performing additional setup...")

            # Replicate ADC gate on extension port X12
            self.handle_error(spcm.spcm_dwSetParam_i32(
                self.card,
                spcm.SPCM_X12_MODE,
                (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH1 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
            ))

            # Replicate unblanking signal at extension port X13
            self.handle_error(spcm.spcm_dwSetParam_i32(
                self.card,
                spcm.SPCM_X13_MODE,
                (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH3 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
            ))

        self.log.debug("Device setup completed")
        # _ = self.get_status()

    def set_gradient_offsets(self, offsets: Dimensions, high_impedance: list[bool] = [True, True, True]) -> None:
        """Set offset values of the gradient output channels.

        Parameters
        ----------
        offsets
            Offset values as Dimension datatype as defined in acquisition parameter

        Returns
        -------
            List of integer values read from card for x, y and z offset values
        """
        # Check card connection
        try:
            if not self.card:
                raise ConnectionError("No connection to TX card.")
        except ConnectionError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Check offset values
        if abs(offsets.x) > self.max_amplitude[1]:
            self.log.error("Gradient offset of channel x exceeds maximum amplitude.")
        if abs(offsets.y) > self.max_amplitude[2]:
            self.log.error("Gradient offset of channel y exceeds maximum amplitude.")
        if abs(offsets.z) > self.max_amplitude[3]:
            self.log.error("Gradient offset of channel z exceeds maximum amplitude.")

        # Extract per channel flag for high impedance termination
        try:
            x_high_imp, y_high_imp, z_high_imp = high_impedance
        except ValueError as err:
            # Raise error if list does not have 3 values to unpack
            self.log.exception(err, exc_info=True)
            raise err

        # Set offset values, scale offset by 0.5 if channel is terminated into high impedance
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_OFFS1, int(offsets.x / 2) if x_high_imp else int(offsets.x))
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_OFFS2, int(offsets.y / 2) if y_high_imp else int(offsets.y))
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_OFFS3, int(offsets.z / 2) if z_high_imp else int(offsets.z))

        # Write setup
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_WRITESETUP)

        # Define variables to read offset values
        offset_x = spcm.int32(0)
        offset_y = spcm.int32(0)
        offset_z = spcm.int32(0)

        # Read offset values from card
        spcm.spcm_dwGetParam_i64(self.card, spcm.SPC_OFFS1, ctypes.byref(offset_x))
        spcm.spcm_dwGetParam_i64(self.card, spcm.SPC_OFFS2, ctypes.byref(offset_y))
        spcm.spcm_dwGetParam_i64(self.card, spcm.SPC_OFFS3, ctypes.byref(offset_z))

        set_offsets = [offset_x.value, offset_y.value, offset_z.value]
        self.log.info("Set gradient values %s mV for x, y and z.", set_offsets)

        # Check values read from card and log error if they are not correct
        if not (set_offsets[0] == offsets.x and set_offsets[1] == offsets.y and set_offsets[2] == offsets.z):
            self.log.error(
                "Actual gradient offsets do not correspond to the values to be set (x=%s, y=%s, z=%s mV)",
                offsets.x, offsets.y, offsets.z
            )

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
            sqnc = data.seq

            # Check if sequence datatype is valid
            if sqnc.dtype != np.int16:
                raise ValueError("Sequence replay data is not int16, please unroll sequence to int16.")

            # Check if card connection is established
            if not self.card:
                raise ConnectionError("No connection to card established...")

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

            self.handle_error(spcm.spcm_dwSetParam_i32(
                self.card,
                spcm.SPC_M2CMD,
                spcm.M2CMD_CARD_STOP | spcm.M2CMD_DATA_STOPDMA,
            ))
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
        # Get total size of data buffer to be played out
        self.data_buffer_size = data.nbytes
        self.log.debug("Replay data buffer: %s bytes", self.data_buffer_size)

        # Calculate notify size is set to 1/16 of the replay buffer size
        # Ensure that minimum notify size is 4096 bytes
        notify_size = spcm.int32(max(4096, min(
            int(((self.data_buffer_size / TX_NOTIFY_RATE) // 4096) * 4096),
            int(((self.max_ring_buffer_size.value / TX_NOTIFY_RATE) // 4096) * 4096),
        )))

        # >> Define software buffer
        # Setup replay data buffer
        data_buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        # Allocate continuous ring buffer with minimimum necessary amount of memory, ensure multiple of notify size
        min_ring_buffer_size = int(np.ceil(self.data_buffer_size / notify_size.value) * notify_size.value)
        # Create page-aligned ring buffer
        ring_buffer = create_dma_buffer(min(self.max_ring_buffer_size.value, min_ring_buffer_size))
        ring_buffer_size = spcm.uint64(len(ring_buffer))

        try:
            # Check if ring buffer size is multiple of 2*num_ch (2 bytes per sample per channel)
            if ring_buffer_size.value % (self.num_ch * 2) != 0:
                raise MemoryError(
                    "Ring buffer size is not a multiple of channel sample product \
                    (number of enables channels times 2 byte per sample)"
                )
            # Check size of data buffer
            if self.data_buffer_size % (self.num_ch * 2) != 0:
                raise MemoryError(
                    "Replay data size is not a multiple of enabled channels times 2 (bytes per sample)..."
                )
        except MemoryError as err:
            self.log.exception(err, exc_info=True)
            raise err

        self.log.debug(
            "Ring buffer size: %s; Notify size: %s",
            ring_buffer_size.value,
            notify_size.value,
        )

        try:
            # Perform initial memory transfer: Fill the whole ring buffer
            if (_ring_buffer_pos := ctypes.cast(ring_buffer, ctypes.c_void_p).value) and \
                (_data_buffer_pos := ctypes.cast(data_buffer, ctypes.c_void_p).value):
                if self.data_buffer_size < ring_buffer_size.value:
                    ctypes.memmove(_ring_buffer_pos, _data_buffer_pos, self.data_buffer_size)
                    transferred_bytes = self.data_buffer_size
                else:
                    ctypes.memmove(_ring_buffer_pos, _data_buffer_pos, ring_buffer_size.value)
                    transferred_bytes = ring_buffer_size.value
            else:
                raise RuntimeError("Could not get ring or data buffer position.")
        except RuntimeError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Perform initial data transfer to completely fill continuous buffer
        spcm.spcm_dwDefTransfer_i64(
            self.card,
            spcm.SPCM_BUF_DATA,
            spcm.SPCM_DIR_PCTOCARD,
            notify_size,
            ring_buffer,
            spcm.uint64(0),
            ring_buffer_size,
        )

        self.handle_error(spcm.spcm_dwSetParam_i64(self.card, spcm.SPC_DATA_AVAIL_CARD_LEN, ring_buffer_size))

        self.log.debug("Starting card memory transfer")
        self.handle_error(spcm.spcm_dwSetParam_i32(
            self.card,
            spcm.SPC_M2CMD,
            spcm.M2CMD_DATA_STARTDMA | spcm.M2CMD_DATA_WAITDMA,
        ))

        # Start card
        self.log.debug("Starting card operation")
        self.handle_error(spcm.spcm_dwSetParam_i32(
            self.card,
            spcm.SPC_M2CMD,
            spcm.M2CMD_CARD_START | spcm.M2CMD_CARD_ENABLETRIGGER,
        ))

        avail_bytes = spcm.int32(0)
        usr_position = spcm.int32(0)
        transfer_count = 0

        while (transferred_bytes < self.data_buffer_size) and not self.is_running.is_set():
            # Read available bytes and user position
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_DATA_AVAIL_USER_LEN, ctypes.byref(avail_bytes))
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_DATA_AVAIL_USER_POS, ctypes.byref(usr_position))

            # Calculate new data for the transfer, when notify_size is available on continous buffer
            if avail_bytes.value >= notify_size.value:
                transfer_count += 1

                ring_buffer_position = ctypes.cast((
                    ctypes.c_char * (self.max_ring_buffer_size.value - usr_position.value)).from_buffer(
                        ring_buffer, usr_position.value), ctypes.c_void_p
                    ).value

                current_data_buffer = ctypes.cast(data_buffer, ctypes.c_void_p).value

                # Get new buffer positions
                if ring_buffer_position and current_data_buffer:
                    data_buffer_position = current_data_buffer + transferred_bytes

                    if (bytes_remaining := self.data_buffer_size - transferred_bytes) >= notify_size.value:
                        # Enough data available -> copy notify size
                        ctypes.memmove(
                            ring_buffer_position,
                            data_buffer_position,
                            notify_size.value,
                        )
                    else:
                        # Not enough data availabe -> set remaining bytes to zero
                        ctypes.memmove(
                            ring_buffer_position,
                            data_buffer_position,
                            bytes_remaining,
                        )
                        ctypes.memset(
                            ring_buffer_position + bytes_remaining,
                            0,
                            notify_size.value - bytes_remaining,
                        )

                    self.handle_error(
                        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_DATA_AVAIL_CARD_LEN, notify_size)
                    )
                    transferred_bytes += notify_size.value

                self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_DATA_WAITDMA))

        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_DATA_WAITDMA))
        self.log.debug("Card operation stopped")
