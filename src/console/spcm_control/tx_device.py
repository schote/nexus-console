"""Implementation of transmit card."""

import ctypes
import logging
import threading

import numpy as np

import console.spcm_control.spcm.pyspcm as spcm
from console.interfaces.acquisition_parameter import Dimensions
from console.spcm_control.abstract_device import SpectrumDevice
from console.spcm_control.spcm.tools import create_dma_buffer, type_to_name
from console.pulseq_interpreter.sequence_provider import SequenceProvider

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
        self.handle_error(
            spcm.spcm_dwSetParam_i32(
                self.card,
                spcm.SPC_CHENABLE,
                spcm.CHANNEL0 | spcm.CHANNEL1 | spcm.CHANNEL2 | spcm.CHANNEL3,
            )
        )

        self.log.info("Setup max. output amplitude: %s.", self.max_amplitude)

        # Use loop to enable and setup active channels
        # Channel 0: RF
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT0, 1))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP0, self.max_amplitude[0]))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER0, self.filter_type[0]))

        # Channel 1: Gradient x, synchronous digital output: gate trigger
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_ENABLEOUT1, 1))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_AMP1, self.max_amplitude[1]))
        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_FILTER1, self.filter_type[1]))

        # Channel 2: Gradient y, synchronous digital output: un-blanking
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
        self.handle_error(
            spcm.spcm_dwSetParam_i32(
                self.card,
                spcm.SPCM_X1_MODE,
                (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH1 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
            )
        )
        # Channel X2: dig. reference signal (15th bit from analog channel 2)
        self.handle_error(
            spcm.spcm_dwSetParam_i32(
                self.card,
                spcm.SPCM_X2_MODE,
                (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH2 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
            )
        )
        # Channel X3: dig. unblanking signal (15th bit of analog channel 3)
        self.handle_error(
            spcm.spcm_dwSetParam_i32(
                self.card,
                spcm.SPCM_X3_MODE,
                (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH3 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
            )
        )

        # >> Setup additional GPIO ports, if extender is available
        if card_features.value & (spcm.SPCM_FEAT_DIG16_FX2 | spcm.SPCM_FEAT_DIG16_SMB):
            self.log.info("IO expansion card with FX2 connector detected, performing additional setup...")

            # Replicate ADC gate on extension port X12
            self.handle_error(
                spcm.spcm_dwSetParam_i32(
                    self.card,
                    spcm.SPCM_X12_MODE,
                    (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH1 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
                )
            )

            # Replicate unblanking signal at extension port X13
            self.handle_error(
                spcm.spcm_dwSetParam_i32(
                    self.card,
                    spcm.SPCM_X13_MODE,
                    (spcm.SPCM_XMODE_DIGOUT | spcm.SPCM_XMODE_DIGOUTSRC_CH3 | spcm.SPCM_XMODE_DIGOUTSRC_BIT15),
                )
            )

        self.log.debug("Device setup completed")

    def set_gradient_offsets(self, offsets: Dimensions, is_50ohms: bool = False) -> None:
        """Set offset values of the gradient output channels.

        Parameters
        ----------
        offsets
            Offset values given by Dimensions interface with integers in mV
        is_50ohms
            Boolean flag indicating if the gradient outputs are terminated into 50 ohms or into high impedance.

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

        # If the outputs are terminated with high impedance, only half of the offsets need to be set,
        # as the value at the card output automatically doubles.
        z_scaling = 1.0 if is_50ohms else 0.5

        # Set offset values, scale offset by 0.5 if channel is terminated into high impedance
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_OFFS1, int(offsets.x * z_scaling))
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_OFFS2, int(offsets.y * z_scaling))
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_OFFS3, int(offsets.z * z_scaling))

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
                offsets.x,
                offsets.y,
                offsets.z,
            )

    def start_operation(self, provider: SequenceProvider | None = None) -> None:
        """Start transmit (TX) card operation."""
        try:
            if not provider:
                raise ValueError("No sequence provider.")

            if not self.card:
                raise ConnectionError("No connection to card established...")
        except Exception as exc:
            self.log.exception(exc, exc_info=True)
            raise exc

        if sqnc_sample_rate := 1 / (provider.config.spcm_dwell_time * 1e6) != self.sample_rate:
            self.log.warning(
                "Sequence sample rate (%s MHz) differs from device sample rate (%s MHz).",
                sqnc_sample_rate,
                self.sample_rate,
            )

        self.is_running.clear()
        self.worker = threading.Thread(target=self._fifo_stream_worker, args=(provider,))
        self.worker.start()

    def stop_operation(self) -> None:
        """Stop card operation by thread event and stop card."""
        if self.worker is not None:
            self.is_running.set()
            self.worker.join()

            self.handle_error(
                spcm.spcm_dwSetParam_i32(
                    self.card,
                    spcm.SPC_M2CMD,
                    spcm.M2CMD_CARD_STOP | spcm.M2CMD_DATA_STOPDMA,
                )
            )
            self.worker = None
        else:
            print("No active replay thread found...")

    def _fifo_stream_worker(self, provider: SequenceProvider) -> None:
        """Continuous FIFO mode stream worker."""

        self.data_buffer_size = provider.sequence_size
        self.log.debug("Replay data buffer: %s bytes", self.data_buffer_size)

        notify_size = spcm.int32(
            max(
                4096,
                min(
                    int(((self.data_buffer_size / TX_NOTIFY_RATE) // 4096) * 4096),
                    int(((self.max_ring_buffer_size.value / TX_NOTIFY_RATE) // 4096) * 4096),
                ),
            )
        )

        # Allocate continuous ring buffer with minimum necessary amount of memory, ensure multiple of notify size
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
            if _ring_buffer_pos := ctypes.cast(ring_buffer, ctypes.c_void_p).value:
                initial_transfer = min(self.data_buffer_size, ring_buffer_size.value)
                provider.copy_to_memory(_ring_buffer_pos, initial_transfer)
                transferred_bytes = initial_transfer
            else:
                raise RuntimeError("Could not get ring buffer position.")
        except RuntimeError as err:
            provider.stop()
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
        self.handle_error(
            spcm.spcm_dwSetParam_i32(
                self.card,
                spcm.SPC_M2CMD,
                spcm.M2CMD_DATA_STARTDMA | spcm.M2CMD_DATA_WAITDMA,
            )
        )

        # Start card
        self.log.debug("Starting card operation")
        self.handle_error(
            spcm.spcm_dwSetParam_i32(
                self.card,
                spcm.SPC_M2CMD,
                spcm.M2CMD_CARD_START | spcm.M2CMD_CARD_ENABLETRIGGER,
            )
        )

        avail_bytes = spcm.int32(0)
        usr_position = spcm.int32(0)
        transfer_count = 0

        while (transferred_bytes < self.data_buffer_size) and not self.is_running.is_set():
            # Read available bytes and user position
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_DATA_AVAIL_USER_LEN, ctypes.byref(avail_bytes))
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_DATA_AVAIL_USER_POS, ctypes.byref(usr_position))

            # Calculate new data for the transfer, when notify_size is available on continuous buffer
            if avail_bytes.value >= notify_size.value:
                transfer_count += 1

                ring_buffer_position = ctypes.cast(
                    (ctypes.c_char * (self.max_ring_buffer_size.value - usr_position.value)).from_buffer(
                        ring_buffer, usr_position.value
                    ),
                    ctypes.c_void_p,
                ).value

                if ring_buffer_position:
                    if (bytes_remaining := self.data_buffer_size - transferred_bytes) >= notify_size.value:
                        provider.copy_to_memory(ring_buffer_position, notify_size.value)
                    else:
                        provider.copy_to_memory(ring_buffer_position, bytes_remaining)
                        ctypes.memset(
                            ring_buffer_position + bytes_remaining,
                            0,
                            notify_size.value - bytes_remaining,
                        )

                    self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_DATA_AVAIL_CARD_LEN, notify_size))
                    transferred_bytes += notify_size.value

                self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_DATA_WAITDMA))

        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_DATA_WAITDMA))
        provider.stop()
        self.log.debug("Card operation stopped")
