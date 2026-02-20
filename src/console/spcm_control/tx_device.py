"""Implementation of transmit card."""

import ctypes
import logging
import multiprocessing
import time
from dataclasses import dataclass
from multiprocessing import shared_memory

import numpy as np

import console.spcm_control.spcm.pyspcm as spcm
from console.interfaces.enums import TxCommand
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.spcm_control.abstract_device import SpectrumDevice
from console.spcm_control.spcm.tools import create_dma_buffer, type_to_name

TX_NOTIFY_RATE = 16


@dataclass(kw_only=True)
class TxCard(SpectrumDevice, multiprocessing.Process):
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

    command_queue: multiprocessing.Queue

    def __init__(
        self,
        path: str,
        max_amplitude: tuple[int, int, int, int],
        filter_type: tuple[int, int, int, int],
        sample_rate: int,
        command_queue: multiprocessing.Queue,
    ) -> None:
        self.log = logging.getLogger(self.__name__)
        multiprocessing.Process.__init__(self, name=self.__name__)
        SpectrumDevice.__init__(self, path=path, log=self.log)

        self.max_amplitude = max_amplitude
        self.filter_type = filter_type
        self.sample_rate = sample_rate
        self.command_queue = command_queue

        # Number of output channels is fixed
        self.num_ch = 4
        # Size of the current sequence
        self.data_buffer_size: int = 0

        # Define maximum ring buffer size, 512 MSamples * 2 Bytes = 1024 MB
        self.max_ring_buffer_size: spcm.uint64 = spcm.uint64(1024**3)

        # Process-local attributes
        self.is_running = None

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

    def set_gradient_offsets(self, offsets: list[int], is_50ohms: bool = False) -> None:
        """Set offset values of the gradient output channels."""
        # ... (impl same as before, but called from run() or via IPC)
        # For simplicity in this refactor, we assume offsets are handled during setup or via commands.
        # But we'll keep the logic for use in the subprocess.
        if not self.card:
            return

        # If the outputs are terminated with high impedance, only half of the offsets need to be set
        z_scaling = 1.0 if is_50ohms else 0.5

        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_OFFS1, int(offsets[0] * z_scaling))
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_OFFS2, int(offsets[1] * z_scaling))
        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_OFFS3, int(offsets[2] * z_scaling))

        spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_CARD_WRITESETUP)
        self.log.info("Set gradient values %s mV for x, y and z.", offsets)

    def run(self) -> None:
        """Main process loop."""
        self.log.info("TX Process started")
        self.card_type = spcm.int32(0)
        self.is_running = multiprocessing.Event()

        try:
            self.connect()
            while True:
                msg = self.command_queue.get()
                if isinstance(msg, dict):
                    cmd = msg.get("event")
                    if cmd == TxCommand.START:
                        num_averages = msg.get("num_averages", 1)
                        averaging_delay = msg.get("averaging_delay", 0.0)
                        shm_name = msg.get("shm_name")
                        sample_count = msg.get("sample_count")

                        self.is_running.clear()
                        for avg in range(num_averages):
                            if self.is_running.is_set():
                                break
                            self.log.info("Starting TX average %s/%s", avg + 1, num_averages)
                            self._fifo_stream_worker(shm_name, sample_count)
                            if avg < num_averages - 1:
                                time.sleep(averaging_delay)
                    elif cmd == TxCommand.STOP:
                        self.is_running.set()
                    elif cmd == TxCommand.SHUTDOWN:
                        self.log.info("TX Process shutting down")
                        break
                elif msg == TxCommand.SHUTDOWN:
                    break
        except Exception as e:
            self.log.exception(f"Error in TX Process: {e}")
        finally:
            self.disconnect()

    def start_operation(self, data: UnrolledSequence | None = None) -> None:
        """Start transmit (TX) scan (from main process)."""
        if not data:
            self.log.error("No unrolled sequence data provided")
            return

        self.command_queue.put(
            {
                "event": TxCommand.START,
                "num_averages": data.parameter.num_averages,
                "averaging_delay": data.parameter.averaging_delay,
                "shm_name": data.shm_tx.name,
                "sample_count": data.sample_count,
            }
        )

    def stop_operation(self) -> None:
        """Stop card operation (from main process)."""
        self.command_queue.put({"event": TxCommand.STOP})

    def shutdown(self):
        """Shutdown process."""
        self.command_queue.put(TxCommand.SHUTDOWN)
        self.join()

    def _fifo_stream_worker(self, shm_name: str, sample_count: int) -> None:
        """Continuous FIFO mode with SharedMemory support."""
        shm_tx = shared_memory.SharedMemory(name=shm_name)
        data = np.ndarray((4 * sample_count,), dtype=np.int16, buffer=shm_tx.buf)

        # Get total size of data buffer to be played out
        self.data_buffer_size = data.nbytes
        self.log.debug("Replay data buffer: %s bytes", self.data_buffer_size)

        # Calculate notify size is set to 1/16 of the replay buffer size
        # Ensure that minimum notify size is 4096 bytes
        notify_size = spcm.int32(
            max(
                4096,
                min(
                    int(((self.data_buffer_size / TX_NOTIFY_RATE) // 4096) * 4096),
                    int(((self.max_ring_buffer_size.value / TX_NOTIFY_RATE) // 4096) * 4096),
                ),
            )
        )

        data_ptr = data.ctypes.data
        # Allocate continuous ring buffer with minimimum necessary amount of memory, ensure multiple of notify size
        min_ring_buffer_size = int(np.ceil(self.data_buffer_size / notify_size.value) * notify_size.value)
        # Create page-aligned ring buffer
        ring_buffer = create_dma_buffer(min(self.max_ring_buffer_size.value, min_ring_buffer_size))
        ring_buffer_size = spcm.uint64(len(ring_buffer))

        # Perform initial transfer
        if self.data_buffer_size < ring_buffer_size.value:
            ctypes.memmove(ctypes.addressof(ring_buffer.contents), data_ptr, self.data_buffer_size)
            transferred_bytes = self.data_buffer_size
        else:
            ctypes.memmove(ctypes.addressof(ring_buffer.contents), data_ptr, ring_buffer_size.value)
            transferred_bytes = ring_buffer_size.value

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

        while (transferred_bytes < self.data_buffer_size) and not self.is_running.is_set():
            # Read available bytes and user position
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_DATA_AVAIL_USER_LEN, ctypes.byref(avail_bytes))
            spcm.spcm_dwGetParam_i32(self.card, spcm.SPC_DATA_AVAIL_USER_POS, ctypes.byref(usr_position))

            # Calculate new data for the transfer, when notify_size is available on continous buffer
            if avail_bytes.value >= notify_size.value:
                ring_buffer_ptr = ctypes.addressof(ring_buffer.contents) + usr_position.value
                data_pos_ptr = data_ptr + transferred_bytes

                if (bytes_remaining := self.data_buffer_size - transferred_bytes) >= notify_size.value:
                    ctypes.memmove(ring_buffer_ptr, data_pos_ptr, notify_size.value)
                else:
                    ctypes.memmove(ring_buffer_ptr, data_pos_ptr, bytes_remaining)
                    ctypes.memset(ring_buffer_ptr + bytes_remaining, 0, notify_size.value - bytes_remaining)

                self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_DATA_AVAIL_CARD_LEN, notify_size))
                transferred_bytes += notify_size.value

                self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_DATA_WAITDMA))

        self.handle_error(spcm.spcm_dwSetParam_i32(self.card, spcm.SPC_M2CMD, spcm.M2CMD_DATA_WAITDMA))
        self.log.debug("Card operation stopped")
        # Don't forget to close SHM view locally
        shm_tx.close()
