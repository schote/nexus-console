"""Implementation of transmit card."""
import ctypes
import threading
from dataclasses import dataclass

import numpy as np

from console.spcm_control.device_interface import SpectrumDevice
from console.spcm_control.spcm.pyspcm import *  # noqa # pylint: disable=unused-wildcard-import
from console.spcm_control.spcm.spcm_tools import create_dma_buffer, translate_status


@dataclass
class TxCard(SpectrumDevice):
    """Implementation of TX device."""

    path: str
    channel_enable: list[int]
    max_amplitude: list[int]
    filter_type: list[int]
    sample_rate: int

    __name__: str = "TxCard"

    def __post_init__(self):
        """Post init function which is required to use dataclass arguments."""
        super().__init__(self.path)

        self.num_channels = int32(0)
        self.num_data_samples = int(0)
        self.data_buffer_size = int(0)

    def setup_card(self):
        # Reset card
        spcm_dwSetParam_i64(self.card, SPC_M2CMD, M2CMD_CARD_RESET)

        # Set trigger
        spcm_dwSetParam_i32(self.card, SPC_TRIG_ORMASK, SPC_TMASK_SOFTWARE)

        # Set clock mode
        spcm_dwSetParam_i32(self.card, SPC_CLOCKMODE, SPC_CM_INTPLL)
        spcm_dwSetParam_i64(
            self.card, SPC_SAMPLERATE, MEGA(self.sample_rate)
        )  # set card sampling rate in MHz

        # Check actual sampling rate
        sample_rate = int64(0)
        spcm_dwGetParam_i64(self.card, SPC_SAMPLERATE, byref(sample_rate))
        print(f"Device sampling rate: {sample_rate.value*1e-6} MHz")
        if sample_rate.value != MEGA(self.sample_rate):
            raise Warning(
                f"Device sample rate {sample_rate.value*1e-6} MHz does not match set sample rate of {self.sample_rate} MHz..."
            )

        # Multi purpose I/O lines
        # spcm_dwSetParam_i32 (self.card, SPCM_X0_MODE, SPCM_XMODE_TRIGOUT) # X0 as gate signal, SPCM_XMODE_ASYNCOUT?
        # spcm_dwSetParam_i32 (self.card, SPCM_X1_MODE, SPCM_XMODE_DISABLE)
        # spcm_dwSetParam_i32 (self.card, SPCM_X2_MODE, SPCM_XMODE_DISABLE)
        # spcm_dwSetParam_i32 (self.card, SPCM_X3_MODE, SPCM_XMODE_DISABLE)

        # Enable and setup channels
        spcm_dwSetParam_i32(
            self.card, SPC_CHENABLE, CHANNEL0 | CHANNEL1 | CHANNEL2 | CHANNEL3
        )

        # Get the number of active channels
        spcm_dwGetParam_i32(self.card, SPC_CHCOUNT, byref(self.num_channels))
        print(f"Number of active channels: {self.num_channels.value}")

        # Use loop to enable and setup active channels
        # Channel 0: RF
        spcm_dwSetParam_i32(self.card, SPC_ENABLEOUT0, self.channel_enable[0])
        spcm_dwSetParam_i32(self.card, SPC_AMP0, self.max_amplitude[0])
        spcm_dwSetParam_i32(self.card, SPC_FILTER0, self.filter_type[0])

        # Channel 1: Gradient x
        spcm_dwSetParam_i32(self.card, SPC_ENABLEOUT1, self.channel_enable[1])
        spcm_dwSetParam_i32(self.card, SPC_AMP1, self.max_amplitude[1])
        spcm_dwSetParam_i32(self.card, SPC_FILTER1, self.filter_type[1])

        # Channel 2: Gradient y
        spcm_dwSetParam_i32(self.card, SPC_ENABLEOUT2, self.channel_enable[2])
        spcm_dwSetParam_i32(self.card, SPC_AMP2, self.max_amplitude[2])
        spcm_dwSetParam_i32(self.card, SPC_FILTER2, self.filter_type[2])

        # Channel 3: Gradient z
        spcm_dwSetParam_i32(self.card, SPC_ENABLEOUT3, self.channel_enable[3])
        spcm_dwSetParam_i32(self.card, SPC_AMP3, self.max_amplitude[3])
        spcm_dwSetParam_i32(self.card, SPC_FILTER3, self.filter_type[3])

        # Setup the card mode
        # FIFO mode
        spcm_dwSetParam_i32(self.card, SPC_CARDMODE, SPC_REP_FIFO_SINGLE)

        # Standard mode
        # spcm_dwSetParam_i32(self.card, SPC_CARDMODE, SPC_REP_STD_SINGLE)
        # spcm_dwSetParam_i64(self.card, SPC_LOOPS, 1)

    def operate(self, data: np.ndarray) -> None:
        # *** Thread testing:
        # print("Operating TX Card...")
        # print(f"Sequence data in thread: {data}")
        # self.progress = 0.
        # for k, _ in enumerate(data):
        #     self.progress = round((k+1)/len(data), 2)
        #     if k == int(len(data)/2):
        #         print("Thrd: Half of sequence data processed...")
        #     time.sleep(0.2)
        # return

        # self._std_example(data)
        # self._fifo_example(data)
        
        # print(f"Card status: {self.get_status()}")

        # Implementation of thread
        event = threading.Event()
        # worker = threading.Thread(target=self._fifo_example, args=(data, event))
        worker = threading.Thread(target=self._fifo_example_single, args=(data, event))
        worker.start()

        # Join after timeout of 3 seconds
        worker.join(2.5)
        event.set()
        worker.join()

        # print("\nThread closed, stopping card...")
        # error = spcm_dwSetParam_i32(
        #     self.card, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA
        # )
        # self.handle_error(error)
        
        # print(f"Card status: {self.get_status()}")

    def _std_example(self, data: np.ndarray):
        if data.dtype != np.int16:
            raise ValueError("Invalid type, require data to be int16.")

        # For standard mode:
        samples_per_channel = int(len(data) / 4)  # Correct?
        # samples_per_channel = int(len(data))
        spcm_dwSetParam_i32(self.card, SPC_MEMSIZE, samples_per_channel)

        # Get pointer to data
        buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        buffer_size = uint64(data.nbytes)

        print("Transfer samples to buffer...")
        # Transfer first <notify-size> chunk of data to DMA
        # spcm_dwDefTransfer_i64 defines the transfer buffer by 2 x 32 bit unsigned integer
        # Function arguments: device, buffer type, direction, notify size, pointer to the data buffer, offset - 0 in FIFO mode, transfer length
        spcm_dwDefTransfer_i64(
            self.card,
            SPCM_BUF_DATA,
            SPCM_DIR_PCTOCARD,
            int32(0),
            buffer,
            uint64(0),
            buffer_size,
        )

        # STANDARD MODE
        # Transfer data, read error, start replay and again read error
        err = spcm_dwSetParam_i32(
            self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA
        )
        self.handle_error(err)
        print("Trigger card...")
        err = spcm_dwSetParam_i32(
            self.card,
            SPC_M2CMD,
            M2CMD_CARD_START | M2CMD_CARD_FORCETRIGGER | M2CMD_CARD_WAITREADY,
        )
        self.handle_error(err)

    def _calc_new_data(
        self, buffer: c_void_p, data: c_void_p, total_bytes: int, bytes_to_copy: int
    ) -> None:
        """
        Function to load a fraction of pre-calculated data from local
        data buffer to the continuous (ring-) buffer on the spectrum card.

        Parameters
        ----------
        buffer
            Pointer to the continous buffer
        data
            Pointer to the buffer with pre-calculated data
        total_bytes
            Total number of bytes transferred
        bytes_to_copy
            Fraction of bytes to copy
        """
        buffer_start_position = total_bytes % self.data_buffer_size  # in bytes
        copied_bytes = 0

        while copied_bytes < bytes_to_copy:
            # copy at most the pre-calculated data, prevent overflow
            copy_bytes = bytes_to_copy - copied_bytes
            if copy_bytes > self.data_buffer_size - buffer_start_position:
                copy_bytes = self.data_buffer_size - buffer_start_position
            # copy data from pre-calculated buffer to DMA buffer
            ctypes.memmove(
                cast(buffer, c_void_p).value + copied_bytes,
                cast(data, c_void_p).value + buffer_start_position,
                copy_bytes,
            )
            copied_bytes += copy_bytes
            buffer_start_position = 0

    def _fifo_example(self, data: np.ndarray, event):
        """Continuous FIFO mode examples.

        Parameters
        ----------
        data
            Numpy array of data to be replayed by card.
            Data should be in the format
            [c0_0, c1_0, c2_0, c3_0, c0_1, c1_1, c2_1, c3_1, ...],
            where cX denotes the channel and the subsequent index the sample index.
        event
            Interrupt thread event to stop infinite loop
        """
        data_buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        self.data_buffer_size = int(data.nbytes)
        self.num_data_samples = int(len(data) / 4)  # number of samples per channel

        notify_size = int32(128 * 1024)  # 128kB

        # Setup software buffer
        cont_buffer = c_void_p()
        cont_buffer_size = uint64(1 * 1024 * 1024)  # 1 MB
        avail_cont_buffer_size = uint64(0)
        spcm_dwGetContBuf_i64(
            self.card, SPCM_BUF_DATA, byref(cont_buffer), byref(avail_cont_buffer_size)
        )

        print(f"Available continuous buffer size: {avail_cont_buffer_size.value}")
        print(f"Desired continuous buffer size: {cont_buffer_size.value}")

        # We try to use a continuous buffer for data transfer or allocate our own buffer in case there’s none
        if avail_cont_buffer_size.value >= cont_buffer_size.value:
            print("INFO: Using continuous buffer.")
        else:
            cont_buffer = create_dma_buffer(cont_buffer_size.value)
            print("INFO: Using buffer allocated by user program.")

        position = 0
        self._calc_new_data(cont_buffer, data_buffer, position, cont_buffer_size.value)
        position += cont_buffer_size.value

        # Define transfer
        spcm_dwDefTransfer_i64(
            self.card,
            SPCM_BUF_DATA,
            SPCM_DIR_PCTOCARD,
            notify_size,
            cont_buffer,
            uint64(0),
            cont_buffer_size,
        )
        spcm_dwSetParam_i64(self.card, SPC_DATA_AVAIL_CARD_LEN, cont_buffer_size)

        # Start DMA
        print("Starting DMA...")
        spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA)

        # status = int32(0)
        available_data = int32(0)
        usr_position = int32(0)
        buffer_level = int32(0)
        card_started = False

        buffer_level_report_counter = 0

        while not event.isSet():
            # Wait for DMA to finish
            error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_WAITDMA)
            if error != ERR_OK:
                if error == ERR_TIMEOUT:
                    print("Timeout...")
                else:
                    self.handle_error(error)
                    break
            else:
                spcm_dwGetParam_i32(
                    self.card, SPC_FILLSIZEPROMILLE, byref(buffer_level)
                )
                if not card_started:
                    if buffer_level.value == 1000:
                        # Start buffer if card buffer level is at 100%
                        error = spcm_dwSetParam_i32(
                            self.card,
                            SPC_M2CMD,
                            M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER,
                        )
                        if error == ERR_TIMEOUT:
                            self.handle_error(error)
                            break
                        card_started = True

                    else:
                        buffer_level_report_counter += 1
                        if buffer_level_report_counter > 10:
                            print(
                                f"Loading initial card buffer data to start card: {buffer_level.value/10}",
                                end="\r",
                                flush=True,
                            )
                            buffer_level_report_counter = 0

                # Read status, update available bytes and position
                # spcm_dwGetParam_i32(self.card, SPC_M2STATUS, byref(status))
                spcm_dwGetParam_i32(
                    self.card, SPC_DATA_AVAIL_USER_LEN, byref(available_data)
                )
                spcm_dwGetParam_i32(
                    self.card, SPC_DATA_AVAIL_USER_POS, byref(usr_position)
                )

                # calculate new data
                if available_data.value >= notify_size.value:
                    new_data = (
                        c_char * (cont_buffer_size.value - usr_position.value)
                    ).from_buffer(cont_buffer, usr_position.value)
                    self._calc_new_data(
                        new_data, data_buffer, position, notify_size.value
                    )
                    spcm_dwSetParam_i32(self.card, SPC_DATA_AVAIL_CARD_LEN, notify_size)
                    position += notify_size.value

        # print("\nStopping card...")
        # # Stop cards
        # error = spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)
        # self.handle_error(error)
        
    def _fifo_example_single(self, data: np.ndarray, event):
        """Continuous FIFO mode examples.

        Parameters
        ----------
        data
            Numpy array of data to be replayed by card.
            Data should be in the format
            [c0_0, c1_0, c2_0, c3_0, c0_1, c1_1, c2_1, c3_1, ...],
            where cX denotes the channel and the subsequent index the sample index.
        event
            Interrupt thread event to stop infinite loop
        """
        print("CARD STATUS: ", self.get_status())
         
        data_buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        self.data_buffer_size = int(data.nbytes)
        self.num_data_samples = int(len(data) / 4)  # number of samples per channel

        notify_size = int32(128 * 1024)  # 128kB

        # Setup software buffer
        cont_buffer = c_void_p()
        cont_buffer_size = uint64(1 * 1024 * 1024)  # 1 MB, approx. 1/5 of total data to replay
        cont_buffer = create_dma_buffer(cont_buffer_size.value)

        # Calculate initial data transfer (size of complete continous buffer)
        total_bytes = 0
        self._calc_new_data(cont_buffer, data_buffer, total_bytes, cont_buffer_size.value)
        total_bytes += cont_buffer_size.value

        # Perform initial data transfer to completely fill continuous buffer
        spcm_dwDefTransfer_i64(self.card, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, notify_size, cont_buffer, 
                               uint64(0), cont_buffer_size)
        spcm_dwSetParam_i64(self.card, SPC_DATA_AVAIL_CARD_LEN, cont_buffer_size)

        print("Starting DMA...")
        error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        self.handle_error(error)
        
        # Start card
        print("Starting card...")
        error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER)
        self.handle_error(error)

        avail_bytes = int32(0)
        usr_position = int32(0)

        # while not event.isSet():
        while total_bytes < self.data_buffer_size:
            # Read available bytes and user position
            spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_LEN, byref(avail_bytes))
            spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_POS, byref(usr_position))
            
            # Calculate new data for the transfer, when notify_size is available on continous buffer
            if avail_bytes.value >= notify_size.value:
                new_data = (c_char * (cont_buffer_size.value - usr_position.value)).from_buffer(cont_buffer, usr_position.value)
                self._calc_new_data(new_data, data_buffer, total_bytes, notify_size.value)
                spcm_dwSetParam_i32(self.card, SPC_DATA_AVAIL_CARD_LEN, notify_size)
                total_bytes += notify_size.value
                
                error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_WAITDMA)
                self.handle_error(error)
        
        # Program stucks at this line
        # print("Waiting for card to finish...")
        # spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_WAITDMA)
        
        # When the previous line is left out, the card stops immediately.
        # In this case, no output is triggered at the oscilloscop.
        # The assumption is, that the card could not even start to replay or 
        # trigger the replay of the waveform.
        # print("\nStopping DMA and card...")
        # error = spcm_dwSetParam_i32(
        #     self.card, 
        #     SPC_M2CMD, 
        #     M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA
        # )
        # self.handle_error(error)
        
        # print(f"Card status: {self.get_status()}")

    def get_status(self) -> dict[str, str]:
        """Get the current card status.

        Returns
        -------
            String with status description.
        """
        if not self.card:
            raise ConnectionError("No spectrum card found.")
        status = int32(0)
        spcm_dwGetParam_i32(self.card, SPC_M2STATUS, byref(status))
        return {
            "code": status.value,
            "msg": translate_status(status.value)
        }

    def output_to_card_value(self, value: int, channel: int = 0) -> int:
        """Calculates int16 value which corresponds to given value in mV.

        Parameters
        ----------
        value
            Value in mV

        Returns
        -------
            Integer card value to get desired output in mV
        """
        if (ratio := value / self.max_amplitude[channel]) > 1:
            raise ValueError("Given value exceeds channel output limit.")
        # Card values written as int16
        return int(ratio * np.iinfo(np.int16).max)
