"""Implementation of transmit card."""
import ctypes
import threading
from dataclasses import dataclass
from pprint import pprint

import numpy as np
from console.spcm_control.device_interface import SpectrumDevice
from console.spcm_control.spcm.pyspcm import *  # noqa # pylint: disable=unused-wildcard-import
from console.spcm_control.spcm.spcm_tools import (create_dma_buffer,
                                                  translate_status)


@dataclass
class TxCard(SpectrumDevice):
    """
    Implementation of TX device.
    
    Implements abstract base class SpectrumDevice, which requires the abstract methods get_status(), setup_card() and operate().
    The TxCard is automatically instantiated by a yaml-loader when loading the configuration file.
    
    The implementation was done and tested with M2p6546-x4.
    - std. memory size: 512 MSample, 2 Bytes/sample => 1024 MB
    
    Overview:
    ---------
    The TX card operates with a ring buffer on the spectrum card, defined by ring_buffer_size.
    The ring buffer is filled in fractions of notify_size.
    """

    path: str
    channel_enable: list[int] = [1, 1, 1, 1]
    max_amplitude: list[int]
    filter_type: list[int]
    sample_rate: int
    notify_rate: int = 16

    __name__: str = "TxCard"

    def __post_init__(self):
        """Post init function which is required to use dataclass arguments."""
        super().__init__(self.path)

        self.num_ch = sum(self.channel_enable)

        # Size of the current sequence 
        self.data_buffer_size = int(0)
        
        # Define ring buffer and notify size
        self.ring_buffer_size: uint64 = uint64(1024**3)  # => 512 MSamples * 2 Bytes = 1024 MB
        # self.ring_buffer_size: uint64 = uint64(1024**2)
        
        # Check if ring buffer size is multiple of num_ch * 2 (channels = sum(channel_enable), 2 bytes per sample)
        if (self.ring_buffer_size.value % (self.num_ch * 2) != 0):
            raise MemoryError("Ring buffer size is not a multiple of channel sample product (number of enables channels times 2 byte per sample)")
        
        if self.ring_buffer_size.value % self.notify_rate == 0:
            self.notify_size = int32(int(self.ring_buffer_size.value/self.notify_rate))
        else:
            # Set default fraktion to 16, notify size equals 1/16 of ring buffer size
            self.notify_size = int32(int(self.ring_buffer_size.value/16))
            
        print(f"Ring buffer size: {self.ring_buffer_size.value}, notify size: ", self.notify_size.value)
        
        # Threading class attributes
        self.worker: threading.Thread | None = None
        self.emergency_stop = threading.Event()
        
            
    def setup_card(self):
        # Reset card
        spcm_dwSetParam_i64(self.card, SPC_M2CMD, M2CMD_CARD_RESET)
        
        # self.print_status() # debug
        # >> TODO: At this point, card alread has M2STAT_CARD_PRETRIGGER and M2STAT_CARD_TRIGGER set, correct?
        
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

        # Enable and setup channels
        spcm_dwSetParam_i32(
            self.card, SPC_CHENABLE, CHANNEL0 | CHANNEL1 | CHANNEL2 | CHANNEL3
        )

        # Use loop to enable and setup active channels
        # Channel 0: RF
        spcm_dwSetParam_i32(self.card, SPC_ENABLEOUT0, self.channel_enable[0])
        spcm_dwSetParam_i32(self.card, SPC_AMP0, self.max_amplitude[0])
        spcm_dwSetParam_i32(self.card, SPC_FILTER0, self.filter_type[0])

        # Channel 1: Gradient x, synchronus digital output: gate trigger
        spcm_dwSetParam_i32(self.card, SPC_ENABLEOUT1, self.channel_enable[1])
        spcm_dwSetParam_i32(self.card, SPC_AMP1, self.max_amplitude[1])
        spcm_dwSetParam_i32(self.card, SPC_FILTER1, self.filter_type[1])

        # Channel 2: Gradient y, synchronus digital output: un-blanking
        spcm_dwSetParam_i32(self.card, SPC_ENABLEOUT2, self.channel_enable[2])
        spcm_dwSetParam_i32(self.card, SPC_AMP2, self.max_amplitude[2])
        spcm_dwSetParam_i32(self.card, SPC_FILTER2, self.filter_type[2])

        # Channel 3: Gradient z
        spcm_dwSetParam_i32(self.card, SPC_ENABLEOUT3, self.channel_enable[3])
        spcm_dwSetParam_i32(self.card, SPC_AMP3, self.max_amplitude[3])
        spcm_dwSetParam_i32(self.card, SPC_FILTER3, self.filter_type[3])

        # Setup the card in FIFO mode
        spcm_dwSetParam_i32(self.card, SPC_CARDMODE, SPC_REP_FIFO_SINGLE)
        
        # >> Setup digital output channels
        # Multi purpose I/O lines for gate and un-blanking
        # spcm_dwSetParam_i32 (self.card, SPCM_X0_MODE, SPCM_XMODE_TRIGOUT)
        # spcm_dwSetParam_i32 (self.card, SPCM_X1_MODE, SPCM_XMODE_TRIGOUT)

        # Analog channel 1 for digital ADC gate signal
        # spcm_dwSetParam_i32(self.card, SPCM_X0_MODE, SPCM_XMODE_DIGOUT | SPCM_XMODE_DIGOUTSRC_CH1 | SPCM_XMODE_DIGOUTSRC_BIT15)
        # Analog channel 2 for digital un-blanking signal
        # spcm_dwSetParam_i32(self.card, SPCM_X1_MODE, SPCM_XMODE_DIGOUT | SPCM_XMODE_DIGOUTSRC_CH2 | SPCM_XMODE_DIGOUTSRC_BIT15)

        print("Setup done, reading status...")
        self.print_status()
        

    def start_operation(self, data: np.ndarray) -> None:
        
        # TODO: Values in data given in V, check if max. amplitude per channel is not exceeded
        # TODO: Convert float values to int16
        # TODO: Add ADC event to one of the gradient channels:
        # >> Shift uint16 values of gradient channels (index 1...3, step_size 4) by one bit to the right
        # >> Reduces precision by one bit, use highest bit (left) to control digital output
        # >> ADC example: ADC on = 1000 0000 0000, combine by XOR/OR? => Test
        
        # Setup card, clear emergency stop thread event and start thread
        self.setup_card()
        self.emergency_stop.clear()
        self.worker = threading.Thread(target=self._streaming, args=(data, ))
        self.worker.start()
        

    def stop_operation(self) -> None:
        if self.worker is not None:
            self.emergency_stop.set()
            self.worker.join()
            
            error = spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)
            self.handle_error(error)
            
            self.worker = None
        else:
            print("No active process found...")
        

    def _streaming(self, data: np.ndarray) -> None:
        """Continuous FIFO mode examples.

        Parameters
        ----------
        data
            Numpy array of data to be replayed by card.
            Replay data should be in the format:
            >>> [c0_0, c1_0, c2_0, c3_0, c0_1, c1_1, c2_1, c3_1, ..., cX_N]
            Here, X denotes the channel and the subsequent index N the sample index.
        """
        # Extend the provided data array with zeros to obtain a multiple of ring buffer size in memory
        # TODO: If replay data << ring buffer size we write a lot of zeros => dynamically adjust ring buffer size?
        if (rest := data.nbytes % self.ring_buffer_size.value) != 0:
            rest = self.ring_buffer_size.value - rest
            if rest % 2 != 0:
                raise MemoryError("Providet data array size is not a multiple of 2 bytes (size of one sample)")
        
            fill_size = int((rest)/2)
            data = np.append(data, np.zeros(fill_size, dtype=np.int16))
            print(f"Appended {fill_size} zeros to data array...")
        
        # Get total size of data buffer to be played out
        self.data_buffer_size = int(data.nbytes)
        if self.data_buffer_size % (self.num_ch * 2) != 0:
            raise MemoryError("Replay data size is not a multiple of enabled channels times 2 (bytes per sample)...")
        data_buffer_samples_per_ch = uint64(int(self.data_buffer_size / (self.num_ch * 2)))
        # Report replay buffer size and samples
        print(f"Replay data buffer size in bytes: {self.data_buffer_size}, number of samples per channel: {data_buffer_samples_per_ch.value}...")
        
        # >> Define software buffer
        # Setup replay data buffer
        data_buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        # Allocate continuous ring buffer as defined by class attribute
        ring_buffer = create_dma_buffer(self.ring_buffer_size.value)

        # Perform initial memory transfer: Fill the whole ring buffer
        ctypes.memmove(cast(ring_buffer, c_void_p).value, cast(data_buffer, c_void_p).value, self.ring_buffer_size.value)
        transferred_bytes = self.ring_buffer_size.value
        print("Initially transferred bytes: ", transferred_bytes)
        
        # Perform initial data transfer to completely fill continuous buffer
        spcm_dwDefTransfer_i64(
            self.card,
            SPCM_BUF_DATA,
            SPCM_DIR_PCTOCARD,
            self.notify_size,
            ring_buffer,
            uint64(0),
            self.ring_buffer_size
        )
        spcm_dwSetParam_i64(self.card, SPC_DATA_AVAIL_CARD_LEN, self.ring_buffer_size)

        print("Starting DMA...")
        error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        self.handle_error(error)
        
        # Start card
        print("Starting card...")
        error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER)
        self.handle_error(error)

        avail_bytes = int32(0)
        usr_position = int32(0)
        transfer_count = 0

        while (transferred_bytes < self.data_buffer_size) and not self.emergency_stop.is_set():
            
            # Read available bytes and user position
            spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_LEN, byref(avail_bytes))
            spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_POS, byref(usr_position))
            
            # Calculate new data for the transfer, when notify_size is available on continous buffer
            if avail_bytes.value >= self.notify_size.value:
                
                transfer_count += 1

                # Get new buffer positions
                ring_buffer_position = cast((c_char * (self.ring_buffer_size.value - usr_position.value)).from_buffer(ring_buffer, usr_position.value), c_void_p).value
                data_buffer_position = cast(data_buffer, c_void_p).value + transferred_bytes
                
                # Move memory: Current ring buffer position, position in sequence data and amount to transfer (=> notify size)
                ctypes.memmove(ring_buffer_position, data_buffer_position, self.notify_size.value)
                
                spcm_dwSetParam_i32(self.card, SPC_DATA_AVAIL_CARD_LEN, self.notify_size)
                transferred_bytes += self.notify_size.value
                
                error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_WAITDMA)
                self.handle_error(error)

        print("FIFO LOOP FINISHED...")
        # Number of transfers equals replay data size / notify size - ring buffer size (initial transfer)
        print(f">> Transferred bytes: {transferred_bytes}, number of transfers: {transfer_count}")

        del data_buffer
        del ring_buffer
        
        self.print_status()
        
        
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
        return status.value
    
    
    def print_status(self, include_desc: bool = False) -> None:
        code = self.get_status()
        msg, bit_reg_rev = translate_status(code, include_desc=include_desc)
        pprint(msg)
        print(f"Status code: {code}, Bit register (reversed): {bit_reg_rev}")


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
