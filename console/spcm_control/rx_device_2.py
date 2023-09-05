"""Implementation of receive card."""
import ctypes
import threading
from dataclasses import dataclass
from datetime import datetime
from pprint import pprint
import numpy as np

from console.spcm_control.device_interface import SpectrumDevice
from console.spcm_control.spcm.pyspcm import *  # noqa # pylint: disable=unused-wildcard-import
from console.spcm_control.spcm.spcm_tools import *  # noqa # pylint: disable=unused-wildcard-import


@dataclass
class RxCard(SpectrumDevice):
    """Implementation of RX device."""

    path: str
    channel_enable: list[int]
    max_amplitude: list[int]
    sample_rate: int
    memory_size: int
    loops: int
    timeStampMode: bool
    __name__: str = "RxCard"

    def __post_init__(self):
        """Execute after init function to do further class setup."""
        super().__init__(self.path)
        self.num_channels = int32(0)
        self.lCardType = int32(0)
        self.lmemory_size = int64(0)
        self.lpost_trigger = int32(0)
        self.ltrigger_delay = int32(0)
        self.lx0_mode = int32(0)

        self.worker: threading.Thread | None = None
        self.emergency_stop = threading.Event()

    #    Maybe create channel enable/disable option for later
    """
    def channel_lookup(self, enableList: list):
        ChannelList     = [CHANNEL0,CHANNEL1,CHANNEL2,CHANNEL3]
        helper          = []
        EnabledChannels = [] 
        
        for i in range (len(enableList)):
            if(enableList[i] == 1):
                helper.append(ChannelList[i])
                EnabledChannels = EnabledChannels | ChannelList[i]
    """

    def setup_card(self):
        # Get the card type and reset card
        spcm_dwGetParam_i32(self.card, SPC_PCITYP, byref(self.lCardType))
        spcm_dwSetParam_i64(self.card, SPC_M2CMD, M2CMD_CARD_RESET)  # Needed?

        # Setup channels
        # Input impdefance and voltage setting for channel0
        # spcm_dwSetParam_i32(self.card, SPC_CHENABLE    , CHANNEL0 | CHANNEL1 | CHANNEL2 | CHANNEL3) #Todo for all channels
        spcm_dwSetParam_i32(self.card, SPC_CHENABLE, CHANNEL0 | CHANNEL1)  # Todo for all channels selectable?
        spcm_dwSetParam_i32(self.card, SPC_50OHM0, 0)  
        spcm_dwSetParam_i32(self.card, SPC_AMP0, self.max_amplitude[0])

        # Input impdefance and voltage setting for channel1, More channels can be added later. TBD.
        spcm_dwSetParam_i32(self.card, SPC_50OHM1, 0) 
        spcm_dwSetParam_i32(self.card, SPC_AMP1, self.max_amplitude[1])

        # Get the number of active channels. This will be needed for handling the buffer size
        spcm_dwGetParam_i32(self.card, SPC_CHCOUNT, byref(self.num_channels))
        print(f"Number of active Rx channels:           {self.num_channels.value}")

        # Some general cards settings
        spcm_dwSetParam_i32(self.card, SPC_DIGITALBWFILTER, 0)  # Digital filter setting for receiver
        
        # Set card sampling rate in MHz
        spcm_dwSetParam_i64(self.card, SPC_SAMPLERATE, MEGA(self.sample_rate))

        # Check actual sampling rate
        sample_rate = int64(0)
        spcm_dwGetParam_i64(self.card, SPC_SAMPLERATE, byref(sample_rate))
        print(f"Rx device sampling rate:                {sample_rate.value*1e-6} MHz")
        if sample_rate.value != MEGA(self.sample_rate):
            raise Warning(
                f"Rx device sample rate                {sample_rate.value*1e-6} MHz does not match set sample rate of {self.sample_rate} MHz..."
            )

        # Set up the pre and post trigger values. Post trigger size is at least one notify size to avoid data loss. 
        self.post_trigger = 4096
        self.pre_trigger = 8  
        
        # Set the memory size, pre and post trigger and loop paramaters
        # spcm_dwSetParam_i32(self.card, SPC_MEMSIZE, self.memory_size)
        spcm_dwSetParam_i32(self.card, SPC_POSTTRIGGER, self.post_trigger)
        spcm_dwSetParam_i32(self.card, SPC_PRETRIGGER, self.pre_trigger)
        spcm_dwSetParam_i32(self.card, SPC_LOOPS, 0) # Loop parameter is zero for infinite loop
        spcm_dwSetParam_i32(self.card, SPC_CLOCKMODE, SPC_CM_INTPLL)  # Set clock mode
        
        # Set timeout to 5s
        spcm_dwSetParam_i32(self.card, SPC_TIMEOUT, 5000)


        # Setup timestamp mode to read number of samples per gate if available
        spcm_dwSetParam_i32(self.card, SPC_TIMESTAMP_CMD, SPC_TSMODE_STARTRESET | SPC_TSCNT_INTERNAL)
            
        spcm_dwSetParam_i32(self.card, SPC_TRIG_EXT1_MODE, SPC_TM_POS)
        spcm_dwSetParam_i32(self.card, SPC_TRIG_ORMASK, SPC_TMASK_EXT1)

        # FIFO mode
        spcm_dwSetParam_i32(self.card, SPC_CARDMODE, SPC_REC_FIFO_GATE)


    def start_operation(self):  # self note: Add type?
        # event = threading.Event()
        
        # Clear the emergency stop flag
        self.emergency_stop.clear()
        
        # Start card thread. if time stamp mode is not available use the example function.
        self.worker = threading.Thread(target=self._fifo_gated_ts)
        self.worker.start()
        
    def stop_operation(self):
        # Stop card thread. Check if thread is running
        if self.worker is not None:
            self.emergency_stop.set()
            self.worker.join()
            
            # Stop the card. We will stop the card in two steps. First we will stop the data transfer and then we will stop the card. If time stamp mode is enabled, we need to stop the extra data transfer as well.
            error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA | M2CMD_EXTRA_STOPDMA)
            
            #Handle error
            self.handle_error(error)
            self.worker = None
            
        # No thread is running
        else:
            print("No active process found...")
    
    def _fifo_gated_ts(self):
        
        
        # >> Define data buffer
        # Define the Rx buffer size. It should be at multiple of 4096 bytes notify size.
        rx_size = 204800
        rx_buffer_size = uint64(rx_size)
        rx_notify= 4096
        rx_notify_size = int32(rx_notify)
        
        # Define Rx Buffer
        rx_data         = np.empty(shape=(1, rx_buffer_size.value * self.num_channels.value), dtype=np.int16)
        rx_buffer       = rx_data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        
        # Write Rx buffer to the card
        spcm_dwDefTransfer_i64(self.card, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, rx_notify_size, rx_buffer, uint64(0), rx_buffer_size)
        
        
        
        
        # >> Define TS buffer
        # TODO: Check if there is a difference to the "create_dma_buffer" function...
        # Define the Rx buffer size. It should be at multiple of 4096 bytes notify size.
        
        ts_buffer_size = uint64(2*4096)
        ts_buffer = c_void_p ()
        ts_buffer = create_dma_buffer(ts_buffer_size.value)
        
        # Define Timestamp buffer
        #ts_data         = np.empty(int(ts_buffer_size.value/2), dtype=np.int16)
        #ts_buffer       = ts_data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
                
        # Define the notify size for rx buffer and timestamps. They should be at multiple of 4096 bytes.
        ts_notify_size = int32(KILO_B(4))

        # Define the transfer buffer for the cards. Please note that the notify size is 4096 bytes, which should be a single page (minimum value for the cards). 
        spcm_dwDefTransfer_i64 (self.card, SPCM_BUF_TIMESTAMP, SPCM_DIR_CARDTOPC, ts_notify_size, ts_buffer, uint64(0), ts_buffer_size)

        pll_data = cast(ts_buffer, ptr64) # cast to pointer to 64bit integer
        rx_data  = cast(rx_buffer, ptr16) # cast to pointer to 16bit integer
        spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_EXTRA_POLL)
        
        
        # >> Start everything
        err = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER | M2CMD_DATA_STARTDMA)
        self.handle_error(err)
        
        available_timestamp_bytes       = int32(0)
        available_timestamp_postion     = int32(0)
        available_user_databytes        = int32(0)
        data_user_position              = int32(0)
        #Flag to check if timestamp is available
        got_timestamp = False
        gate_read_progress = False
        head = False
        gate_length = 0
        number_of_gates_to_read = 0
        total_transferred = 0
        counter = 0
        counter2 = 0
        bytes_to_read = 0
        lBitsPerSample = int32 (0)
        spcm_dwGetParam_i32 (self.card, SPC_MIINST_BITSPERSAMPLE, byref (lBitsPerSample))
        print(f"Bits per sample: {lBitsPerSample.value}")
        while not self.emergency_stop.is_set():
            spcm_dwGetParam_i64(self.card, SPC_TS_AVAIL_USER_LEN, byref(available_timestamp_bytes))
            if available_timestamp_bytes.value >= 32:
                # read position 
                spcm_dwGetParam_i64(self.card, SPC_TS_AVAIL_USER_POS, byref(available_timestamp_postion))
                
                # Read two timestamps
                timestamp1          = pll_data[int(available_timestamp_postion.value/8)]  / (self.sample_rate*1e6)
                timestamp0          = pll_data[int(available_timestamp_postion.value/8)+2] / (self.sample_rate*1e6)
                timeStampDifference = timestamp0 - timestamp1
                
                # print("Read time interval: ", timeStampDifference)
                print("Timestamps: ", (timestamp0, timestamp1))
                # ts = [val / self.sample_rate for val in pll_data]
                # print("Timestamp values: ", ts)
                got_timestamp = True
                number_of_gates_to_read += 1 #Maybe not needed at the moment
                gate_length = int((timeStampDifference)*self.sample_rate*1e6)
                print("Gate length in samples ", (gate_length, timeStampDifference))
                spcm_dwSetParam_i32(self.card, SPC_TS_AVAIL_CARD_LEN, 32)
            
            while (got_timestamp and number_of_gates_to_read>0):
                spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_WAITDMA)
                if (gate_read_progress==False):
                    print("Start reading gate")
                    #f0_i = np.zeros(gate_length, dtype=np.complex128)
                    #f1_i = np.zeros(gate_length, dtype=np.complex128)
                   
                    gate_read_progress = True
                    head = True
                else:
                    spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_LEN, byref(available_user_databytes))
                    print("Available user data bytes: ", available_user_databytes.value)
                    if available_user_databytes.value >= rx_notify_size.value: # Add pre and post trigger
                        # The data is available. We can read the data now. Get the data position in the card.
                        spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_POS, byref(data_user_position))
                        print("Data user position: ", data_user_position.value)
                        if(head):
                            print("init buffers")
                            f0_i = np.zeros(gate_length, dtype=np.complex128)
                            f1_i = np.zeros(gate_length, dtype=np.complex128)
                            head = False
                            host_buffer_index = data_user_position.value + self.num_channels.value*8 # subtract the 8 bytes for the pretrigger
                            bytes_to_read = gate_length*self.num_channels.value*2 # 2 bytes per sample
                            gate_read_progress = True
                        else:
                            host_buffer_index = data_user_position.value 
                        print("host_buffer_index: ", host_buffer_index)
                        if(bytes_to_read >= available_user_databytes.value):
                            print("bytesto read: ", bytes_to_read)
                            for bufferIndex in range(1,int(available_user_databytes.value/(self.num_channels.value*2))):
                                counterX = host_buffer_index + (self.num_channels.value * bufferIndex)
                                f0_i[bufferIndex - 1] = np.complex_(float(rx_data[counterX - 1])
                                )    # Type is complex at the moment we can change it later
                                f1_i[bufferIndex - 1] = np.complex_(float(rx_data[counterX]))
                            counter += available_user_databytes.value
                            bytes_to_read = bytes_to_read - available_user_databytes.value
                            spcm_dwSetParam_i32(self.card, SPC_DATA_AVAIL_CARD_LEN, available_user_databytes.value)#*self.num_channels.value)
                            
                        else:
                            print("bytesto read all: ", bytes_to_read)
                            for bufferIndex in range(1,int(bytes_to_read/(self.num_channels.value*2))):
                                counterX = host_buffer_index + (self.num_channels.value * bufferIndex)
                                f0_i[bufferIndex - 1] = np.complex_(float(rx_data[counterX - 1])
                                )    # Type is complex at the moment we can change it later
                                f1_i[bufferIndex - 1] = np.complex_(float(rx_data[counterX]))
                            counter = counter + bytes_to_read
                            bytes_to_read = 0
                            print(f"Got total samples...        {counter}")
                            #print(f"Got samples per channel...  {counter2}")
                            rx_time = datetime.now().strftime("%Y%m%d-%H%M%S")
                            print(rx_time)
                            np.save(f"rx_{rx_time}_{timestamp0}_{timestamp1}.npy", f1_i) #Channel 1
                            f0_i = np.zeros(gate_length, dtype=np.complex128)
                            f1_i = np.zeros(gate_length, dtype=np.complex128)
                            number_of_gates_to_read -= 1
                            spcm_dwSetParam_i32(self.card, SPC_DATA_AVAIL_CARD_LEN, bytes_to_read)#*self.num_channels.value)
                            gate_read_progress = False
                            head = True
                            if(number_of_gates_to_read == 0):
                                got_timestamp = False
                # Count the number of samples. This is useful when we know how many samples are transferred from the Txcard.
                #total_transferred += int((rx_notify_size.value)/4)
                #number_of_samples_transferred += rx_notify_size.value/2
              
                
                
                
 

    def get_status(self):
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
        msg, bit_reg_rev = translate_status(code, include_desc=include_desc)
        pprint(msg)
        print(f"Status code: {code}, Bit register (reversed): {bit_reg_rev}")
