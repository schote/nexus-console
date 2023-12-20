"""Implementation of receive card."""
import logging
import threading
from ctypes import POINTER, addressof, byref, c_short, cast, sizeof
from dataclasses import dataclass
from decimal import Decimal, getcontext
from itertools import compress

import numpy as np

import console.spcm_control.spcm.pyspcm as sp
from console.spcm_control.abstract_device import SpectrumDevice
from console.spcm_control.spcm.tools import create_dma_buffer, translate_status, type_to_name

# Define registers lists
CH_SELECT = [
    sp.CHANNEL0,
    sp.CHANNEL1,
    sp.CHANNEL2,
    sp.CHANNEL3,
    sp.CHANNEL4,
    sp.CHANNEL5,
    sp.CHANNEL6,
    sp.CHANNEL7,
]
AMP_SELECT = [
    sp.SPC_AMP0,
    sp.SPC_AMP1,
    sp.SPC_AMP2,
    sp.SPC_AMP3,
    sp.SPC_AMP4,
    sp.SPC_AMP5,
    sp.SPC_AMP6,
    sp.SPC_AMP7,
]
IMP_SELECT = [
    sp.SPC_50OHM0,
    sp.SPC_50OHM1,
    sp.SPC_50OHM2,
    sp.SPC_50OHM3,
    sp.SPC_50OHM4,
    sp.SPC_50OHM5,
    sp.SPC_50OHM6,
    sp.SPC_50OHM7,
]


# Set precision for precise gate samples calculation
getcontext().prec = 28


@dataclass
class RxCard(SpectrumDevice):
    """Implementation of RX device."""

    path: str
    sample_rate: int
    channel_enable: list[int]
    max_amplitude: list[int]
    impedance_50_ohms: list[int]

    __name__: str = "RxCard"

    def __post_init__(self):
        """Execute after init function to do further class setup."""
        self.log = logging.getLogger(self.__name__)
        super().__init__(self.path, log=self.log)
        self.num_channels = sp.int32(0)
        self.card_type = sp.int32(0)

        self.worker: threading.Thread | None = None
        self.is_running = threading.Event()

        # Define pre and post trigger time.
        # Pre trigger is set to minimum and post trigger size is at least one notify size to avoid data loss.
        self.pre_trigger = 8
        self.post_trigger = 4096
        self.post_trigger_size = 0  # TODO: only use one variable for post trigger

        self.rx_data = []
        self.rx_scaling = [amp / (2**15) for amp in self.max_amplitude]

    def dict(self) -> dict:
        """Returnt class variables which are json serializable as dictionary.

        Returns
        -------
            Dictionary containing class variables.
        """
        return super().dict()

    def setup_card(self):
        """Set up spectrum card in transmit (TX) mode.

        At the very beginning, a card reset is performed. The clock mode is set according to the sample rate,
        defined by the class attribute.
        Two receive channels are enables and configured by max. amplitude according to class variables and impedance.

        Raises
        ------
        Warning
            The actual set sample rate deviates from the corresponding class attribute to be set,
            class attribute is overwritten.
        """
        # Get the card type and reset card
        sp.spcm_dwGetParam_i32(self.card, sp.SPC_PCITYP, byref(self.card_type))
        sp.spcm_dwSetParam_i64(self.card, sp.SPC_M2CMD, sp.M2CMD_CARD_RESET)  # Needed?

        try:
            if "M2p.59" not in (device_type := type_to_name(self.card_type.value)):
                raise ConnectionError("Device with path %s is of type %s, no receive card" % (self.path, device_type))
        except ConnectionError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Setup the internal clockmode, clock output enable (use RX clock output to enable anti-alias filter)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CLOCKMODE, sp.SPC_CM_INTPLL)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CLOCKOUT, 1)

        # Use external clock: Terminate to 50 Ohms, set threshold to 1.5V, suitable for 3.3V clock
        # sp.spcm_dwSetParam_i32(self.card, sp.SPC_CLOCKMODE, sp.SPC_CM_EXTERNAL)
        # sp.spcm_dwSetParam_i32(self.card, sp.SPC_CLOCK50OHM, 1)
        # sp.spcm_dwSetParam_i32(self.card, sp.SPC_CLOCK_THRESHOLD, 1500)

        # Set card sampling rate in MHz and read the actual sampling rate
        sp.spcm_dwSetParam_i64(self.card, sp.SPC_SAMPLERATE, sp.MEGA(self.sample_rate))
        sample_rate = sp.int64(0)
        sp.spcm_dwGetParam_i64(self.card, sp.SPC_SAMPLERATE, byref(sample_rate))
        self.log.info("Device sampling rate: %s MHz", sample_rate.value * 1e-6)

        if sample_rate.value != sp.MEGA(self.sample_rate):
            self.log.warning(
                "Actual device sample rate %s MHz does not match set sample rate of %s MHz; Updating class attribute",
                sample_rate.value * 1e-6,
                self.sample_rate,
            )
            self.sample_rate = int(sample_rate.value * 1e-6)

        # Check channel enable, max. amplitude per channel and impedance values
        try:
            # if (num_enable := len(self.channel_enable)) < 1 or num_enable > 8:
            if (num_enable := len(self.channel_enable)) != 8:
                raise ValueError("Channel enable list is incomplete: %s/8" % num_enable)
            # Impedance and amplitude configuration lists must match the channel enable list len
            if (num_imp := len(self.impedance_50_ohms)) != num_enable:
                raise ValueError("Channel impedance list is incomplete: %s/8" % num_imp)
            if (num_amp := len(self.max_amplitude)) != num_enable:
                raise ValueError("channel max. amplitude list is incomplete: %s/8" % num_amp)
            if not np.log2(num_enable).is_integer():
                raise ValueError("Invalid number of enabled channels, must be power of 2.")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Enable receive channels, compress list of channel select registers to obtain list of channels to be enabled
        # Sum of the compressed list equals logical or operator
        # e.g. sp.CHANNEL0 | sp.CHANNEL1 | sp.CHANNEL5 = sum([sp.CHANNEL0, sp.CHANNEL1, sp.CHANNEL5]) = 35
        channel_selection = sum(list(compress(CH_SELECT, map(bool, self.channel_enable))))
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CHENABLE, channel_selection)

        # Set impedance and amplitude limits for each channel according to device configuration
        for k, enable in enumerate(map(bool, self.channel_enable)):
            if enable:
                self.log.info(
                    "Channel %s enabled; 50 ohms impedance: %s; Max. amplitude: %s mV",
                    k,
                    self.impedance_50_ohms[k],
                    self.max_amplitude[k],
                )
                sp.spcm_dwSetParam_i32(self.card, IMP_SELECT[k], self.impedance_50_ohms[k])
                sp.spcm_dwSetParam_i32(self.card, AMP_SELECT[k], self.max_amplitude[k])

        # Get the number of actual active channels and compare against provided channel enable list
        sp.spcm_dwGetParam_i32(self.card, sp.SPC_CHCOUNT, byref(self.num_channels))
        try:
            self.log.info(
                "Number of enabled receive channels (read from card): %s",
                self.num_channels.value,
            )
            if not self.num_channels.value == sum(self.channel_enable):
                raise ValueError("Actual number of enabled channels does not match the provided channel enable list")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Digital filter setting for receiver, 0 = disable digital bandwidth filter
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_DIGITALBWFILTER, 0)

        # Setup digital input channels for reference signal
        sp.spcm_dwSetParam_i32(self.card, sp.SPCM_X2_MODE, sp.SPCM_XMODE_DIGIN)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_DIGMODE0, (sp.DIGMODEMASK_BIT15 & sp.SPCM_DIGMODE_X2))

        # TODO: Double check, why is the post trigger divided by number of channels and multiplied by 2?
        self.post_trigger = 4096 // self.num_channels.value
        self.post_trigger_size = self.post_trigger * 2
        # Set the memory size, pre and post trigger and loop paramaters, SPC_LOOPS = 0 => runs infinitely long
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_POSTTRIGGER, self.post_trigger)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_PRETRIGGER, self.pre_trigger)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_LOOPS, 0)

        # Setup timestamp mode to read number of samples per gate if available
        sp.spcm_dwSetParam_i32(
            self.card,
            sp.SPC_TIMESTAMP_CMD,
            sp.SPC_TSMODE_STARTRESET | sp.SPC_TSCNT_INTERNAL,
        )
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TRIG_EXT1_MODE, sp.SPC_TM_POS)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TRIG_ORMASK, sp.SPC_TMASK_EXT1)

        # Setup gated fifo mode
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CARDMODE, sp.SPC_REC_FIFO_GATE)

        # Set timeout to 10ms (used for DMA wait)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TIMEOUT, 10)

        self.log.debug("Device setup completed")
        self.log_card_status()

    def start_operation(self):
        """Start card operation."""
        # Clear the emergency stop flag
        self.is_running.clear()
        self.rx_data = []
        # Start card thread. if time stamp mode is not available use the example function.
        self.worker = threading.Thread(target=self._gated_timestamps_stream)
        self.worker.start()

    def stop_operation(self):
        """Stop card thread."""
        # Check if thread is running
        if self.worker is not None:
            self.is_running.set()
            self.worker.join()

            # Stop the card. We will stop the card in two steps.
            # First we will stop the data transfer and then we will stop the card.
            # If time stamp mode is enabled, we need to stop the extra data transfer as well.
            error = sp.spcm_dwSetParam_i32(
                self.card,
                sp.SPC_M2CMD,
                sp.M2CMD_CARD_STOP | sp.M2CMD_DATA_STOPDMA | sp.M2CMD_EXTRA_STOPDMA,
            )
            self.handle_error(error)
            self.worker = None
        else:
            # No thread is running
            self.log.error("No active process found")

    def _gated_timestamps_stream(self):
        # >> Define RX data buffer
        # RX buffer size must be a multiple of notify size. Min. notify size is 4096 bytes/4 kBytes.
        rx_notify = sp.int32(sp.KILO_B(4))

        # Buffer size set to maximum. Todo check one ADC window is not exceeding the limit
        rx_size = 1024**3
        rx_buffer_size = sp.uint64(rx_size)

        rx_buffer = create_dma_buffer(rx_buffer_size.value)
        sp.spcm_dwDefTransfer_i64(
            self.card,
            sp.SPCM_BUF_DATA,
            sp.SPCM_DIR_CARDTOPC,
            rx_notify,
            rx_buffer,
            sp.uint64(0),
            rx_buffer_size,
        )

        # >> Define TS buffer
        # Define the timestamps notify size. Min. notify size is 4096 bytes.
        ts_notify = sp.int32(sp.KILO_B(4))
        # Define timestamp buffer, must be multiple of timestamps notify size
        ts_buffer_size = sp.uint64(2 * 4096)

        ts_buffer = create_dma_buffer(ts_buffer_size.value)
        sp.spcm_dwDefTransfer_i64(
            self.card,
            sp.SPCM_BUF_TIMESTAMP,
            sp.SPCM_DIR_CARDTOPC,
            ts_notify,
            ts_buffer,
            sp.uint64(0),
            ts_buffer_size,
        )

        pll_data = cast(ts_buffer, sp.ptr64)  # cast to pointer to 64bit integer
        rx_data = cast(rx_buffer, sp.ptr16)  # cast to pointer to 16bit integer

        # Setup polling mode
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_EXTRA_POLL)

        # TODO: Move all the stuff up to here to setup function?

        # >> Start everything
        err = sp.spcm_dwSetParam_i32(
            self.card,
            sp.SPC_M2CMD,
            sp.M2CMD_CARD_START | sp.M2CMD_CARD_ENABLETRIGGER | sp.M2CMD_DATA_STARTDMA,
        )
        self.handle_error(err)

        available_timestamp_bytes = sp.int32(0)
        available_timestamp_postion = sp.int32(0)
        available_user_databytes = sp.int32(0)
        data_user_position = sp.int32(0)
        total_gates = 0
        bytes_leftover = 0
        total_leftover = 0

        # Start receiver
        self.log.debug("Starting receive")

        while not self.is_running.is_set():
            sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_DATA_WAITDMA)
            sp.spcm_dwGetParam_i64(self.card, sp.SPC_TS_AVAIL_USER_LEN, byref(available_timestamp_bytes))
            if available_timestamp_bytes.value >= 32:
                # read position
                sp.spcm_dwGetParam_i64(
                    self.card,
                    sp.SPC_TS_AVAIL_USER_POS,
                    byref(available_timestamp_postion),
                )

                # Read two timestamps
                timestamp_0 = pll_data[int(available_timestamp_postion.value / 8)] / (self.sample_rate * 1e6)
                timestamp_1 = pll_data[int(available_timestamp_postion.value / 8) + 2] / (self.sample_rate * 1e6)

                # Calculate gate duration
                gate_length = Decimal(str(timestamp_1)) - Decimal(str(timestamp_0))

                # Calculate the number of adc gate sample points (per channel)
                gate_sample = int(gate_length * (Decimal(str(self.sample_rate)) * Decimal("1e6")))

                self.log.info(
                    "Gate: (%s s, %s s); ADC duration: %s ms ; Gate Sample: % s",
                    timestamp_0,
                    timestamp_1,
                    gate_length,  # Can be trimmed.
                    gate_sample,
                )

                sp.spcm_dwSetParam_i32(self.card, sp.SPC_TS_AVAIL_CARD_LEN, 32)
                sp.spcm_dwGetParam_i64(
                    self.card,
                    sp.SPC_TS_AVAIL_USER_LEN,
                    byref(available_timestamp_bytes),
                )

                # Check for rounding errors
                total_bytes = (gate_sample + self.pre_trigger) * 2 * self.num_channels.value
                bytes_sequence = (gate_sample + self.pre_trigger + self.post_trigger) * 2 * self.num_channels.value

                # Read/update available user bytes
                sp.spcm_dwGetParam_i32(
                    self.card,
                    sp.SPC_DATA_AVAIL_USER_LEN,
                    byref(available_user_databytes),
                )
                sp.spcm_dwGetParam_i32(self.card, sp.SPC_DATA_AVAIL_USER_POS, byref(data_user_position))

                # Debug log statements
                # self.log.debug("Available timestamp buffer size: %s", available_timestamp_bytes.value)
                self.log.debug("Expected adc data in bytes: %s", total_bytes)
                self.log.debug("User position (adc buffer): %s", data_user_position.value)
                self.log.debug("Number of segments in notify size: %s", total_bytes // rx_notify.value)
                self.log.debug("Left over in bytes: %s", bytes_leftover)

                while not self.is_running.is_set():
                    # Read/update available user bytes
                    sp.spcm_dwGetParam_i32(
                        self.card,
                        sp.SPC_DATA_AVAIL_USER_LEN,
                        byref(available_user_databytes),
                    )
                    self.log.debug("Available user length in bytes (adc buffer): %s", available_user_databytes.value)

                    if available_user_databytes.value >= total_bytes:
                        total_gates += 1

                        sp.spcm_dwGetParam_i32(
                            self.card,
                            sp.SPC_DATA_AVAIL_USER_POS,
                            byref(data_user_position),
                        )

                        byte_position = data_user_position.value // 2
                        total_bytes_to_read = available_user_databytes.value
                        index_0 = byte_position + total_leftover // 2

                        if total_bytes_to_read + data_user_position.value >= rx_size:
                            # >> We need two indices in case of memory position overflows the total memory length
                            # Get the last position available and subtract it from current byte position
                            index_1 = rx_size // 2 - index_0

                            # Get the remaining length after overflow. Then subtract it from the total bytes.
                            index_2 = total_bytes // 2 - index_1

                            # Numpy array conversation. Get the first part of the slice
                            offset_bytes_1 = index_1 * sizeof(c_short)
                            ptr_to_slice_1 = cast(addressof(rx_data.contents) + offset_bytes_1, POINTER(c_short))
                            slice_1 = np.ctypeslib.as_array(ptr_to_slice_1, ((index_1),))

                            # Get the second part of the numpy slice
                            offset_bytes_2 = index_2 * sizeof(c_short)
                            ptr_to_slice_2 = cast(addressof(rx_data.contents) + offset_bytes_2, POINTER(c_short))
                            slice_2 = np.ctypeslib.as_array(ptr_to_slice_2, ((index_2),))

                            # Combine the slices
                            gate_data = np.concatenate((slice_1, slice_2))

                        else:
                            # If there is no memory position overflow, just get the data.
                            offset_bytes = index_0 * sizeof(c_short)
                            ptr_to_slice = cast(addressof(rx_data.contents) + offset_bytes, POINTER(c_short))
                            gate_data = np.ctypeslib.as_array(ptr_to_slice, ((total_bytes // 2),))

                        # Cut the pretrigger, we do not need it.
                        pre_trigger_cut = (self.pre_trigger) * self.num_channels.value
                        gate_data = gate_data[pre_trigger_cut:]
                        self.rx_data.append(gate_data.reshape((self.num_channels.value, gate_sample), order="F"))

                        # Most probably we have not filled the whole page. There should be some bytes in the buffer, which are not readable yet.
                        bytes_leftover = (total_bytes + self.post_trigger_size) % rx_notify.value

                        # Calculate the accumulation of the leftover bytes. If it is bigger than the notify value read the page.
                        total_leftover += bytes_leftover
                        if total_leftover >= rx_notify.value:
                            total_leftover = total_leftover - rx_notify.value
                            available_card_len = bytes_sequence - (bytes_leftover) + rx_notify.value
                        else:
                            available_card_len = bytes_sequence - (bytes_leftover)

                        # Tell the card that we have read the data.
                        # It is better for tracking if the card length is in the order of notify (page) size.
                        sp.spcm_dwSetParam_i32(self.card, sp.SPC_DATA_AVAIL_CARD_LEN, available_card_len)
                        break


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
        status = sp.int32(0)
        sp.spcm_dwGetParam_i32(self.card, sp.SPC_M2STATUS, byref(status))
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
