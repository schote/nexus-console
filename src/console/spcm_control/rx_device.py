"""Implementation of receive card."""

import logging
import threading
import time
from ctypes import POINTER, addressof, byref, c_short, cast
from dataclasses import dataclass
from itertools import compress
from multiprocessing import Queue as MpQueue

import numpy as np

import console.spcm_control.spcm.pyspcm as sp
from console.interfaces.rx_data import RxData
from console.pulseq_interpreter.sequence_provider import NUM_REFERENCE_SAMPLES
from console.spcm_control.abstract_device import SpectrumDevice
from console.spcm_control.spcm.tools import create_dma_buffer, type_to_name

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


@dataclass
class RxCard(SpectrumDevice):
    """Implementation of RX device."""

    __name__: str = "RxCard"

    def __init__(
        self,
        path: str,
        sample_rate: int,
        channel_enable: tuple[bool, ...],
        max_amplitude: tuple[int, ...],
        impedance_50_ohms: tuple[bool, ...],
    ) -> None:
        """Execute after init function to do further class setup."""
        self.log = logging.getLogger(self.__name__)
        super().__init__(path, log=self.log)

        self.sample_rate = sample_rate
        self.channel_enable = [int(val) for val in channel_enable]
        self.max_amplitude = max_amplitude
        self.impedance_50_ohms = [int(val) for val in impedance_50_ohms]
        self.rx_data: None | list[RxData] = None

        self.num_channels = sp.int32(0)
        self.card_type = sp.int32(0)

        self.worker: threading.Thread | None = None
        self.is_running = threading.Event()
        self.is_receiving = threading.Event()
        self._total_gates: int = 0

        # Pre trigger is set to minimum, post trigger depends on active channel count and is defined later.
        self.pre_trigger: int = 8
        self.post_trigger: None | int = None

        self.rx_scaling = [amp / (2**15) for amp in self.max_amplitude]

        # Processing queue (set externally by AcquisitionControl)
        self.processing_queue: MpQueue | None = None
        self.queue_index_offset: int = 0

    @property
    def total_gates(self) -> int:
        """ "Helper function to return the number of gates that have been collected by the Rx Card."""
        return self._total_gates

    def setup_card(self):
        """Set up spectrum card in transmit (Rx) mode.

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
            # Check that the length of the channel enable list is 8
            # this has to be true for cards with fewer channels too
            if (num_enable := len(self.channel_enable)) != 8:
                raise ValueError("Channel enable list is incomplete: %s/8" % num_enable)
            # Impedance and amplitude configuration lists must also be of length 8
            if (num_imp := len(self.impedance_50_ohms)) != 8:
                raise ValueError("Channel impedance list is incomplete: %s/8" % num_imp)
            if (num_amp := len(self.max_amplitude)) != 8:
                raise ValueError("channel max. amplitude list is incomplete: %s/8" % num_amp)
            # Number of enabled channels must be either 1, 2, 4 or 8
            if not np.log2(sum(self.channel_enable)).is_integer():
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

        # Configure X2 as digital input for phase reference signal and sample it in sync with analog channel 0
        sp.spcm_dwSetParam_i32(self.card, sp.SPCM_X2_MODE, sp.SPCM_XMODE_DIGIN)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_DIGMODE0, (sp.DIGMODEMASK_BIT15 & sp.SPCM_DIGMODE_X2))

        # Calculate trigger size depending on the number of active channels
        # Since data can only be gathered in notify size chunks, post_trigger // channel_count should be at least one
        # notify size to ensure that we can always access the full gate data.
        self.post_trigger = 4096 // self.num_channels.value

        # Set the memory size, pre and post trigger and loop parameters, SPC_LOOPS = 0 => runs infinitely long
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_POSTTRIGGER, self.post_trigger)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_PRETRIGGER, self.pre_trigger)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_LOOPS, 0)

        # Setup timestamp mode to read number of samples per gate if available
        sp.spcm_dwSetParam_i32(
            self.card,
            sp.SPC_TIMESTAMP_CMD,
            sp.SPC_TSMODE_STARTRESET | sp.SPC_TSCNT_INTERNAL,
        )
        # Configure trigger on EXT1 channel; and trigger on positive edge
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TRIG_EXT1_MODE, sp.SPC_TM_POS)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TRIG_ORMASK, sp.SPC_TMASK_EXT1)

        # Setup gated FIFO mode
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CARDMODE, sp.SPC_REC_FIFO_GATE)

        # Get gate length alignment, number of samples must be integer multiple of this
        gate_alignment = sp.int64(0)
        sp.spcm_dwGetParam_i64(self.card, sp.SPC_GATE_LEN_ALIGNMENT, byref(gate_alignment))
        self.gate_alignment = gate_alignment.value
        self.log.debug("Alignment samples: %d samples" % (self.gate_alignment))

        # Set timeout used for DMA wait to 10 ms
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TIMEOUT, 10)

        self.log.debug("Device setup completed")

    def start_operation(self):
        """Start card operation."""
        # Clear the emergency stop flag
        self.is_running.clear()
        self.is_receiving.clear()

        # Start card thread. if time stamp mode is not available use the example function.
        self.worker = threading.Thread(target=self._gated_timestamps_stream)
        self.worker.start()

    def stop_operation(self):
        """Stop card thread."""
        # Check if thread is running
        if self.worker is not None:
            # Signal thread to stop
            self.is_running.set()
            # Wait for thread to complete
            self.worker.join()

            # Stop card operation with the following steps:
            # 1. Stop card acquisition
            # 2. Stop data DMA transfer
            # 3. Stop timestamp DMA transfer
            self.handle_error(
                sp.spcm_dwSetParam_i32(
                    self.card,
                    sp.SPC_M2CMD,
                    sp.M2CMD_CARD_STOP | sp.M2CMD_DATA_STOPDMA | sp.M2CMD_EXTRA_STOPDMA,
                )
            )
        else:
            # No thread is running
            self.log.error("No active process found")

    def _gated_timestamps_stream(self):
        # Rx buffer size must be a multiple of notify size. Min. notify size is 4096 bytes/4 kBytes.
        rx_notify = sp.int32(sp.KILO_B(4))

        # Buffer size set to maximum.
        rx_size = 1024**3
        rx_buffer_size = sp.uint64(rx_size)

        # Create DMA buffer for receive data and tell the card to use it
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

        # Define the timestamps notify size. Min. notify size is 4096 bytes.
        ts_notify = sp.int32(sp.KILO_B(4))
        # Define timestamp buffer size, must be multiple of timestamps notify size
        ts_buffer_size = sp.uint64(2 * 4096)

        # Create DMA buffer for timestamp data and tell the card to use it
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
        adc_data = cast(rx_buffer, sp.ptr16)  # cast to pointer to 16bit integer

        # Setup polling mode for timestamp data
        self.handle_error(sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_EXTRA_POLL))

        # Start card acquisition and DMA usage
        self.handle_error(
            sp.spcm_dwSetParam_i32(
                self.card,
                sp.SPC_M2CMD,
                sp.M2CMD_CARD_START | sp.M2CMD_CARD_ENABLETRIGGER | sp.M2CMD_DATA_STARTDMA,
            )
        )

        # Define helpers/buffer to read card parameter
        available_timestamp_bytes = sp.int32(0)
        available_timestamp_position = sp.int32(0)
        available_data_bytes = sp.int32(0)
        available_data_position = sp.int32(0)

        # Track bytes from incomplete gate reads for next iteration
        remaining_bytes = 0
        # Track the amount of gate events recorded
        self._total_gates = 0

        # Check that the list of RxData objects has been passed
        if self.rx_data is None:
            self.log.critical("No RxData objects found for storing ADC data")
            raise RuntimeError("No RxData objects found for storing ADC data")

        # Signal that acquisition has started
        self.log.debug("Starting receive")
        self.is_receiving.set()

        while not self.is_running.is_set():
            # Read the available timestamp buffer size
            sp.spcm_dwGetParam_i64(self.card, sp.SPC_TS_AVAIL_USER_LEN, byref(available_timestamp_bytes))

            # Process, if buffer size is greater or equal 32 (corresponds to 2 timestamps)
            if available_timestamp_bytes.value >= 32:
                # Read timestamp position
                sp.spcm_dwGetParam_i32(
                    self.card,
                    sp.SPC_TS_AVAIL_USER_POS,
                    byref(available_timestamp_position),
                )

                # Read exactly two timestamps
                timestamp_0 = pll_data[int(available_timestamp_position.value / 8)]
                timestamp_1 = pll_data[int(available_timestamp_position.value / 8) + 2]

                # Calculate gate duration and the number of adc gate sample points (per channel)
                num_gate_samples = timestamp_1 - timestamp_0
                gate_duration = num_gate_samples / (self.sample_rate * 1e6)

                self.log.info(
                    "Gate: (%s s, %s s); ADC duration: %s ms ; Samples/gate/channel: %s",
                    timestamp_0 / (self.sample_rate * 1e6),
                    timestamp_1 / (self.sample_rate * 1e6),
                    float(gate_duration) * 1e3,  # Can be trimmed.
                    num_gate_samples,
                )

                # Tell buffer 32 bytes were read from timestamp buffer
                try:
                    self.handle_error(sp.spcm_dwSetParam_i32(self.card, sp.SPC_TS_AVAIL_CARD_LEN, 32))
                except RuntimeError:  # Reraise error for traceability
                    raise RuntimeError

                # Calculate size of relevant data (pre_trigger needed to get position of start of gate)
                # This is the minimum amount of data  must be available to get full gate data
                total_bytes_gate = (num_gate_samples + self.pre_trigger) * 2 * self.num_channels.value
                # Get the total data duration, including post trigger, to accurately track buffer position
                samples_sequence = num_gate_samples + self.pre_trigger + self.post_trigger
                # Ensure data alignment
                alignment_samples = samples_sequence % self.gate_alignment
                samples_sequence += alignment_samples
                bytes_sequence = samples_sequence * 2 * self.num_channels.value

                # Check if total gate data does not exceed buffer size
                if bytes_sequence > rx_size:
                    error_msg = (
                        f"ADC gate data ({bytes_sequence} bytes) exceeds "
                        f"available buffer ({rx_size} bytes). "
                        f"Reduce adc length, sample rate or channel count"
                    )
                    self.log.critical(error_msg)
                    raise ValueError(error_msg)

                # Wait for ADC data to arrive in DMA buffer
                try:
                    self.handle_error(sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_DATA_WAITDMA))
                except RuntimeError as e:  # Reraise error for traceability
                    self.log.error(f"DMA wait failed with error: {e}")
                    break

                # Read available data length and position
                sp.spcm_dwGetParam_i32(self.card, sp.SPC_DATA_AVAIL_USER_POS, byref(available_data_position))
                sp.spcm_dwGetParam_i32(self.card, sp.SPC_DATA_AVAIL_USER_LEN, byref(available_data_bytes))

                # # Debug log statements
                self.log.debug(
                    "ADC event size: %d bytes, Available data length: %s bytes"
                    % (total_bytes_gate, available_data_bytes.value)
                )

                # If insufficient data is in buffer wait for more to arrive.
                if available_data_bytes.value + remaining_bytes < total_bytes_gate:
                    # Wait for sufficient data to come in
                    wait_start = time.time()
                    while (
                        available_data_bytes.value + remaining_bytes < total_bytes_gate
                    ) and not self.is_running.is_set():
                        try:
                            self.handle_error(sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_DATA_WAITDMA))
                        except RuntimeError as e:  # Reraise error for traceability
                            self.log.error(f"DMA wait failed with error: {e}")
                            break
                        sp.spcm_dwGetParam_i32(self.card, sp.SPC_DATA_AVAIL_USER_LEN, byref(available_data_bytes))
                    self.log.debug(f"Waited {(time.time() - wait_start) * 1e3:.3f} ms for extra data to enter buffer")

                if remaining_bytes + available_data_bytes.value > rx_size:
                    error_msg = (
                        f"Memory overflow. Sum of remaining bytes ({remaining_bytes} bytes) "
                        f"and newly available bytes ({available_data_bytes.value} bytes) "
                        f"exceeds receive buffer size ({rx_size} bytes)"
                    )
                    self.log.critical(error_msg)
                    raise MemoryError(error_msg)

                # Check if sufficient data is available (while loop doesn't guarantee it since it can be interrupted)
                if available_data_bytes.value + remaining_bytes >= total_bytes_gate:
                    # Adjust memory position to account for bytes remaining after previous acquisition
                    byte_position = available_data_position.value - remaining_bytes

                    # Handle buffer wraparound
                    if byte_position + total_bytes_gate >= rx_size:
                        # Calculate number of bytes to end of buffer
                        bytes_to_end = rx_size - byte_position
                        # calculates number of samples to end of buffer (2 bytes per sample)
                        samples_to_end = bytes_to_end // 2
                        # Get the remaining number of samples after overflow
                        samples_leftover = total_bytes_gate // 2 - samples_to_end

                        # Get the first part of the data
                        # Handle edge case when memory position is exactly at end
                        if samples_to_end == 0:
                            slice_1 = np.array([], dtype=np.int16)
                        else:
                            ptr_to_slice_1 = cast(addressof(adc_data.contents) + byte_position, POINTER(c_short))
                            slice_1 = np.ctypeslib.as_array(ptr_to_slice_1, (samples_to_end,))

                        # Get the second part of the numpy slice
                        ptr_to_slice_2 = cast(addressof(adc_data.contents), POINTER(c_short))
                        slice_2 = np.ctypeslib.as_array(ptr_to_slice_2, (samples_leftover,))

                        # Combine the slices
                        gate_data = np.concatenate((slice_1, slice_2))

                    else:
                        # If there is no memory position overflow, just get the data.
                        ptr_to_slice = cast(addressof(adc_data.contents) + byte_position, POINTER(c_short))
                        gate_data = np.ctypeslib.as_array(ptr_to_slice, ((total_bytes_gate // 2),))

                    # Cut the pretrigger (we don't need it) and reshape the data to (num_coils, num_samples)
                    pre_trigger_cut = (self.pre_trigger) * self.num_channels.value
                    gate_data = gate_data[pre_trigger_cut:].reshape(
                        (self.num_channels.value, num_gate_samples),
                        order="F",
                    )
                    # Store raw data (15 bit) in RxData object, 16th is the digital phase reference
                    rx_data_item = self.rx_data[self._total_gates]
                    rx_data_item.write_raw_data(gate_data << 1)
                    rx_data_item.phase_reference = (
                        gate_data[0, 0 : min(num_gate_samples, NUM_REFERENCE_SAMPLES)].astype(np.uint16) >> 15
                    ).copy()
                    rx_data_item.scaling_factor = self.rx_scaling[: self.num_channels.value]
                    rx_data_item.time_stamp = timestamp_0 / (self.sample_rate * 1e6)

                    if self.processing_queue is not None:
                        global_index = self.queue_index_offset + self._total_gates
                        self.processing_queue.put((global_index, rx_data_item))
                        # Release reference from rx_data list; shared memory stays alive in AcquisitionControl
                        self.rx_data[self._total_gates] = None

                    # Store raw data in RxData object (in the following referenced as `gate`)
                    gate = self.rx_data[self._total_gates]
                    gate.raw_data = gate_data.copy()
                    # Shift bits of first channel, which contains digital phase reference in 16th bit
                    gate.raw_data[0] = (gate.raw_data[0].view(np.uint16) << 1).view(np.int16)
                    # Extract the reference signal (only 16th bit)
                    reference_len = min(num_gate_samples, NUM_REFERENCE_SAMPLES)
                    gate.phase_reference = (gate_data[0, :reference_len].astype(np.uint16) >> 15).copy()
                    gate.scaling_factor = self.rx_scaling[:self.num_channels.value]
                    gate.time_stamp = timestamp_0 / (self.sample_rate * 1e6)

                    # The accumulation of the leftover bytes is positive,
                    # if if the post-trigger event was not fully captured (accumulated sum increases),
                    # or negative if more then the expected data could be read due to lefter bytes
                    # from a previous acquisition (accumulated sum decreases).
                    remaining_bytes += available_data_bytes.value - bytes_sequence

                    self._total_gates += 1

                    # Tell the card that data has been read and the buffer can be reused.
                    # Using the size of available data bytes prevents invalid values.
                    try:
                        self.handle_error(
                            sp.spcm_dwSetParam_i32(self.card, sp.SPC_DATA_AVAIL_CARD_LEN, available_data_bytes)
                        )
                    except RuntimeError:  # Reraise error for traceability
                        raise RuntimeError

                else:
                    self.log.error(
                        "Needed at least %d bytes but only %d bytes available"
                        % (total_bytes_gate, available_data_bytes.value)
                    )

        self.log.debug("Card operation stopped")
