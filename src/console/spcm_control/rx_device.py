"""Implementation of receive card."""
import threading
from ctypes import byref, cast
from dataclasses import dataclass
from pprint import pprint
import logging
import console.spcm_control.spcm.pyspcm as sp
from console.spcm_control.device_interface import SpectrumDevice
from console.spcm_control.spcm.tools import create_dma_buffer, translate_status, type_to_name


@dataclass
class RxCard(SpectrumDevice):
    """Implementation of RX device."""

    path: str
    channel_enable: list[int]
    max_amplitude: list[int]
    sample_rate: int
    memory_size: int
    loops: int
    timestamp_mode: bool
    
    __name__: str = "RxCard"

    def __post_init__(self):
        """Execute after init function to do further class setup."""
        self.log = logging.getLogger('RxDev')
        super().__init__(self.path, log=self.log)
        self.num_channels = sp.int32(0)
        self.card_type = sp.int32(0)

        self.worker: threading.Thread | None = None
        self.emergency_stop = threading.Event()

        # Define pre and post trigger time.
        # Pre trigger is set to minimum and post trigger size is at least one notify size to avoid data loss.
        self.pre_trigger = 8
        self.post_trigger = 4096
        self.post_trigger_size = 0  # TODO: only use one variable for post trigger

        self.rx_data = []
        self.rx_scaling = [amp / (2**15) for amp in self.max_amplitude]

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

        if "M2p.59" not in (device_type := type_to_name(self.card_type.value)):
            raise ConnectionError(f"RX:> Device with path {self.path} is of type {device_type}, no receive card...")

        # Setup the clockmode
        # Internal:
        # sp.spcm_dwSetParam_i32(self.card, sp.SPC_CLOCKMODE, sp.SPC_CM_INTPLL)
        # Use external clock: Terminate to 50 Ohms, set threshold to 1.5V, suitable for 3.3V clock
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CLOCKMODE, sp.SPC_CM_EXTERNAL)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CLOCK50OHM, 1)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CLOCK_THRESHOLD, 1500)

        # Setup analog input channels
        # Enable channel 0 and 1, set impedance and max. amplitude
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CHENABLE, sp.CHANNEL0 | sp.CHANNEL1)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_50OHM0, 0)     # 0 = 1 Mohms, 1 = 50 ohms, check preamp output?
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_50OHM1, 0)     # 0 = 1 Mohms, 1 = 50 ohms, check preamp output?
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_AMP0, self.max_amplitude[0])
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_AMP1, self.max_amplitude[1])
        
        # Setup digital input channels
        sp.spcm_dwSetParam_i32(self.card, sp.SPCM_X2_MODE, sp.SPCM_XMODE_DIGIN)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_DIGMODE0, (sp.DIGMODEMASK_BIT15 & sp.SPCM_DIGMODE_X2))

        # Get the number of active channels. This will be needed for handling the buffer size
        sp.spcm_dwGetParam_i32(self.card, sp.SPC_CHCOUNT, byref(self.num_channels))
        # print(f"RX:> Number of active channels: {self.num_channels.value}")

        # Some general cards settings
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_DIGITALBWFILTER, 0)  # Digital filter setting for receiver

        # Set card sampling rate in MHz
        sp.spcm_dwSetParam_i64(self.card, sp.SPC_SAMPLERATE, sp.MEGA(self.sample_rate))

        # Check actual sampling rate
        sample_rate = sp.int64(0)
        sp.spcm_dwGetParam_i64(self.card, sp.SPC_SAMPLERATE, byref(sample_rate))
        print(f"RX:> Device sampling rate: {sample_rate.value*1e-6} MHz")
        if sample_rate.value != sp.MEGA(self.sample_rate):
            raise Warning(
                f"RX:> Rx device sample rate {sample_rate.value*1e-6} MHz does not match the \
                    set sample rate of {self.sample_rate} MHz..."
            )

        # TODO: Double check, why is the post trigger divided by number of channels and multiplied by 2?
        self.post_trigger = 4096 // self.num_channels.value
        self.post_trigger_size = self.post_trigger * 2

        # Set the memory size, pre and post trigger and loop paramaters
        # spcm_dwSetParam_i32(self.card, SPC_MEMSIZE, self.memory_size)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_POSTTRIGGER, self.post_trigger)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_PRETRIGGER, self.pre_trigger)
        # Loop parameter is zero for infinite loop
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_LOOPS, 0)

        # Set timeout to 10ms
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TIMEOUT, 10)

        # Setup timestamp mode to read number of samples per gate if available
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TIMESTAMP_CMD, sp.SPC_TSMODE_STARTRESET | sp.SPC_TSCNT_INTERNAL)

        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TRIG_EXT1_MODE, sp.SPC_TM_POS)
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_TRIG_ORMASK, sp.SPC_TMASK_EXT1)

        # FIFO mode
        sp.spcm_dwSetParam_i32(self.card, sp.SPC_CARDMODE, sp.SPC_REC_FIFO_GATE)

    def start_operation(self):
        """Start card operation."""
        # Clear the emergency stop flag
        self.emergency_stop.clear()
        self.rx_data = []

        # Start card thread. if time stamp mode is not available use the example function.
        self.worker = threading.Thread(target=self._gated_timestamps_stream)
        self.worker.start()

    def stop_operation(self):
        """Stop card thread."""
        # Check if thread is running
        if self.worker is not None:
            # print("RX:> Stopping card...")
            self.emergency_stop.set()
            self.worker.join()

            # Stop the card. We will stop the card in two steps.
            # First we will stop the data transfer and then we will stop the card.
            # If time stamp mode is enabled, we need to stop the extra data transfer as well.
            error = sp.spcm_dwSetParam_i32(
                self.card, sp.SPC_M2CMD, sp.M2CMD_CARD_STOP | sp.M2CMD_DATA_STOPDMA | sp.M2CMD_EXTRA_STOPDMA
            )

            # Handle error
            self.handle_error(error)
            self.worker = None

        # No thread is running
        else:
            print("RX:> No active process found...")

    def _gated_timestamps_stream(self):
        # >> Define RX data buffer
        # RX buffer size must be a multiple of notify size. Min. notify size is 4096 bytes/4 kBytes.
        rx_notify = sp.int32(sp.KILO_B(4))
        rx_size = rx_notify.value * 400
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
            self.card, sp.SPC_M2CMD, sp.M2CMD_CARD_START | sp.M2CMD_CARD_ENABLETRIGGER | sp.M2CMD_DATA_STARTDMA
        )
        self.handle_error(err)

        available_timestamp_bytes = sp.int32(0)
        available_timestamp_postion = sp.int32(0)
        available_user_databytes = sp.int32(0)
        data_user_position = sp.int32(0)
        total_gates = 0
        bytes_leftover = 0
        total_leftover = 0

        # print("RX:> Starting receiver...")

        while not self.emergency_stop.is_set():
            sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_DATA_WAITDMA)
            sp.spcm_dwGetParam_i64(self.card, sp.SPC_TS_AVAIL_USER_LEN, byref(available_timestamp_bytes))
            if available_timestamp_bytes.value >= 32:
                # read position
                sp.spcm_dwGetParam_i64(self.card, sp.SPC_TS_AVAIL_USER_POS, byref(available_timestamp_postion))

                # Read two timestamps
                timestamp_0 = pll_data[int(available_timestamp_postion.value / 8)] / (self.sample_rate * 1e6)
                timestamp_1 = pll_data[int(available_timestamp_postion.value / 8) + 2] / (self.sample_rate * 1e6)
                gate_length = timestamp_1 - timestamp_0

                # print(f"RX:> Timestamps: {(timestamp_0, timestamp_1)}s, difference: {round(gate_length*1e3, 2)}ms")
                print(f"RX:> Gate: ({timestamp_0}s, {timestamp_1}s); ADC duration: {round(gate_length*1e3, 2)}ms")

                sp.spcm_dwSetParam_i32(self.card, sp.SPC_TS_AVAIL_CARD_LEN, 32)

                sp.spcm_dwGetParam_i64(self.card, sp.SPC_TS_AVAIL_USER_LEN, byref(available_timestamp_bytes))
                # print(f"RX:> Available TS buffer size: {available_timestamp_bytes.value}")

                gate_sample = int(gate_length * self.sample_rate * 1e6)  # number of adc gate sample points per channel

                # Check for rounding errors
                total_bytes = (gate_sample + self.pre_trigger) * 2 * self.num_channels.value
                # page_align = total_bytes + (rx_notify.value - int(total_bytes % rx_notify.value))

                bytes_sequence = (gate_sample + self.pre_trigger + self.post_trigger) * 2 * self.num_channels.value

                # Read/update available user bytes
                sp.spcm_dwGetParam_i32(self.card, sp.SPC_DATA_AVAIL_USER_LEN, byref(available_user_databytes))
                sp.spcm_dwGetParam_i32(self.card, sp.SPC_DATA_AVAIL_USER_POS, byref(data_user_position))

                # Debug statements
                # print(f"RX:> Available user length: {available_user_databytes.value}")
                # print(f"RX:> User position: {data_user_position.value}")
                # print(f"RX:> Expected gate data in bytes: {total_bytes}")
                # print(f"RX:> Segments in notify size: {(total_bytes//rx_notify.value)}")
                # print(f"RX:> Left Over: {bytes_leftover}")
                # print(f"RX:> Page align: {page_align}")

                while not self.emergency_stop.is_set():
                    # Read/update available user bytes
                    sp.spcm_dwGetParam_i32(self.card, sp.SPC_DATA_AVAIL_USER_LEN, byref(available_user_databytes))
                    # print("RX:> Available user length: ", available_user_databytes.value)
                    if available_user_databytes.value >= total_bytes:
                        total_gates += 1

                        # print("RX:> Getting RX buffer read position and RX data...")
                        sp.spcm_dwGetParam_i32(self.card, sp.SPC_DATA_AVAIL_USER_POS, byref(data_user_position))

                        byte_position = data_user_position.value // 2
                        total_bytes_to_read = available_user_databytes.value
                        index_0 = byte_position + total_leftover // 2

                        if total_bytes_to_read + data_user_position.value >= rx_size:
                            # print(f"RX:> Rx_size: {rx_size}")
                            # >> We need two indices in case of memory overflow
                            index_1 = rx_size // 2 - (index_0)
                            index_2 = total_bytes_to_read // 2 - index_1
                            # print(f"RX:> indexes: {index_1, index_2,(index_0-bytes_leftover)}")
                            gate_data = rx_data[index_0 : index_0 + index_1]
                            gate_data += rx_data[0:index_2]
                        else:
                            gate_data = rx_data[index_0 : index_0 + int(total_bytes / 2)]

                        # Truncate gate signal, throw pre-trigger
                        self.rx_data.append([gate_data[0::2][self.pre_trigger :], gate_data[1::2][self.pre_trigger :]])
                        # self.rx_data.append([gate_data[0::2][self.pre_trigger :] << 1, gate_data[1::2][self.pre_trigger :]])
                        # self.ref_data.append(gate_data[0::2][self.pre_trigger :] >> 15)

                        bytes_leftover = (total_bytes + self.post_trigger_size) % rx_notify.value
                        total_leftover += bytes_leftover

                        if total_leftover >= rx_notify.value:
                            total_leftover = total_leftover - rx_notify.value
                            available_card_len = bytes_sequence - (bytes_leftover) + rx_notify.value
                        else:
                            available_card_len = bytes_sequence - (bytes_leftover)

                        # print(f"RX:> Bytes leftover: {bytes_leftover}")

                        # Tell the card that we have read the data.
                        # The card length should be in the order of notify size.
                        sp.spcm_dwSetParam_i32(self.card, sp.SPC_DATA_AVAIL_CARD_LEN, available_card_len)
                        bytes_leftover = (total_bytes + self.post_trigger_size) % rx_notify.value

                        sp.spcm_dwGetParam_i32(self.card, sp.SPC_DATA_AVAIL_USER_LEN, byref(available_user_databytes))

                        # print("RX:> Available user length: ", available_user_databytes.value)
                        break

                    sp.spcm_dwSetParam_i32(self.card, sp.SPC_M2CMD, sp.M2CMD_DATA_WAITDMA)

        # print("RX:> Stopping acquisition...")

    def get_status(self) -> int:
        """Get the current card status.

        Returns
        -------
            String with status description.
        """
        if not self.card:
            raise ConnectionError("RX:> No spectrum card found.")
        status = sp.int32(0)
        sp.spcm_dwGetParam_i32(self.card, sp.SPC_M2STATUS, byref(status))
        return status.value

    def print_status(self, include_desc: bool = False) -> None:
        """Print current card status.

        The status is represented by a list. Each entry represents a possible card status in form
        of a (sub-)list. It contains the status code, name and (optional) description of the spectrum
        instrumentation manual.

        Parameters
        ----------
        include_desc, optional
            Flag which indicates if description string should be contained in status entry, by default False
        """
        code = self.get_status()
        msg, _ = translate_status(code, include_desc=include_desc)
        pprint(msg)
        print(f"RX:> Status code: {code}")
