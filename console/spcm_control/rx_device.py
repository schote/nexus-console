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
        spcm_dwSetParam_i32(self.card, SPC_MEMSIZE, self.memory_size)
        spcm_dwSetParam_i32(self.card, SPC_POSTTRIGGER, self.post_trigger)
        spcm_dwSetParam_i32(self.card, SPC_PRETRIGGER, self.pre_trigger)
        spcm_dwSetParam_i32(self.card, SPC_LOOPS, self.loops) # Loop parameter is zero for infinite loop
        spcm_dwSetParam_i32(self.card, SPC_CLOCKMODE, SPC_CM_INTPLL)  # Set clock mode
        # spcm_dwSetParam_i32(self.card, SPC_CLOCKOUT, 1)  # Output clock , TBD if we need to sync the cards.
        
        # Setup timestamp mode to read number of samples per gate if available
        if (self.timeStampMode):
            spcm_dwSetParam_i32(self.card,SPC_TIMESTAMP_CMD,SPC_TSMODE_STARTRESET | SPC_TSCNT_INTERNAL)
            #spcm_dwSetParam_i32(self.card,SPC_TIMESTAMP_CMD,SPC_TS_RESET)
            print("Time Stamps are enabled")
        else:
            print("Time Stamps are not enabled")
            
        spcm_dwSetParam_i32(self.card, SPC_TRIG_EXT1_MODE, SPC_TM_POS)
        #        spcm_dwSetParam_i32 (self.card, SPC_TRIG_TERM, 1)     #If we use analog trigger
        #        spcm_dwSetParam_i32 (self.card, SPC_TRIG_EXT0_LEVEL0, 1000)
        spcm_dwSetParam_i32(self.card, SPC_TRIG_ORMASK, SPC_TMASK_EXT1)

        spcm_dwGetParam_i32(self.card, SPC_MEMSIZE      , byref(self.lmemory_size)) # Read memory size
        spcm_dwGetParam_i32(self.card, SPC_POSTTRIGGER  , byref(self.lpost_trigger))    # Read post trigger
        spcm_dwGetParam_i32(self.card, SPC_TRIG_DELAY   , byref(self.ltrigger_delay))   # Trigger delay
        spcm_dwGetParam_i32(self.card, SPCM_X1_MODE     , byref(self.lx0_mode))         # X0_mode , Can be used as trigger.

        print(f"Rx device memory size:                  {self.lmemory_size}"   )
        print(f"Post trigger time:                      {self.lpost_trigger}")  # todo calculate and write time units
        print(f"Trigger delay is:                       {self.ltrigger_delay}")  # todo calculate and write time units
        print(f"X0 mode is:                             {self.lx0_mode}")
       
        # FIFO mode
        spcm_dwSetParam_i32(self.card, SPC_CARDMODE, SPC_REC_FIFO_GATE)
        # Single mode
        # spcm_dwSetParam_i32 (self.card, SPC_CARDMODE    , SPC_REC_STD_SINGLE    )

    def start_operation(self):  # self note: Add type?
        # event = threading.Event()
        
        # Clear the emergency stop flag
        self.emergency_stop.clear()
        
        # Start card thread. if time stamp mode is not available use the example function.
        if (self.timeStampMode):
            self.worker = threading.Thread(target=self._FIFO_gated_mode_TS)
        else:
            self.worker = threading.Thread(target=self._FIFO_gated_mode_example)
        self.worker.start()
        
    def stop_operation(self):
        # Stop card thread. Check if thread is running
        if self.worker is not None:
            self.emergency_stop.set()
            self.worker.join()
            
            # Stop the card. We will stop the card in two steps. First we will stop the data transfer and then we will stop the card. If time stamp mode is enabled, we need to stop the extra data transfer as well.
            if (self.timeStampMode):
                error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA | M2CMD_EXTRA_STOPDMA)
            else:
                error = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)
            
            #Handle error
            self.handle_error(error)
            self.worker = None
            
        # No thread is running
        else:
            print("No active process found...")
    
    def _FIFO_gated_mode_TS(self):
        # Define the Rx buffer size. It should be at multiple of 4096 bytes notify size.
        rx_size = 204800
        rx_buffer_size = uint64(rx_size)
        ts_buffer_size = uint64(4096)
        
        # Define Rx Buffer
        rx_data         = np.empty(shape=(1, rx_buffer_size.value * self.num_channels.value), dtype=np.int16)
        rx_buffer       = rx_data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        
        # Define Timestamp buffer
        ts_data         = np.empty(shape=(1, ts_buffer_size.value), dtype=np.int16)
        ts_buffer       = ts_data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
                
        # Define the notify size for rx buffer and timestamps. They should be at multiple of 4096 bytes.
        rx_notify= 4096*10
        rx_notify_size = int32(rx_notify)
        ts_notify_size = int32(4096)
                
        # Write Rx buffer to the card
        spcm_dwDefTransfer_i64(
            self.card, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, rx_notify_size, rx_buffer, uint64(0), rx_buffer_size)
                
        # Define the transfer buffer for the cards. Please note that the notify size is 4096 bytes, which should be a single page (minimum value for the cards). 
        spcm_dwDefTransfer_i64 (self.card, SPCM_BUF_TIMESTAMP, SPCM_DIR_CARDTOPC, ts_notify_size, ts_buffer, 0, ts_buffer_size)
        
        # Define a timeout for the DMA. We will not wait more than 10 seconds if there is no upcoming data. 
        spcm_dwSetParam_i32(
            self.card, SPC_TIMEOUT, 5000
        )
        # Enable the polling mode for timestamp data because the data rate for timestamp is very low.
        spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_EXTRA_POLL)
        
        # The required settings are complete. We can start the cards now
        err = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER |M2CMD_DATA_STARTDMA)
        self.handle_error(err)
        print("Rx card is started....")
        #spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        # Card status register
        card_staus                      = 0
        
        # The following registers are used to read the data from the card.
        available_user_databytes        = int32()
        data_user_position              = int32()
        number_of_samples_transferred   = 0
        total_transferred               = 0
        
        # The following registers are used to read the timestamp data from the card.
        available_timestamp_bytes       = int32()
        available_timestamp_postion     = int32()
        
        f0_i = np.zeros((rx_buffer_size.value), dtype=np.complex128)
        f1_i = np.zeros((rx_buffer_size.value), dtype=np.complex128)
        counter = 0
        counter2 = 0
        # Define an infinite loop to read continously the card data. Until user stops the process.
        while not self.emergency_stop.is_set():
            
            # Wait for data to be available by cards. The data should be at least 4K for the current notify size setting. Please check Notify size for further data. 
            spcm_dwSetParam_i32(self.card, SPC_M2CMD,  M2CMD_DATA_WAITDMA)
            self.handle_error(err)
            #spcm_dwGetParam_i32 (self.card, SPC_M2STATUS,            byref (card_staus))
            card_staus = self.get_status()
            msg, bit_reg_rev = translate_status(card_staus, False)
            #print(bit_reg_rev[8])
            if(bit_reg_rev[8] != '1'): #M2STAT_DATA_BLOCKREADY
                print(available_user_databytes.value)
                if(card_staus == M2STAT_DATA_OVERRUN):
                    print("Data overrun error") #Todo: Handle error
                elif(available_user_databytes.value <= rx_notify):
                    print(f"Got total samples...        {counter}")
                    print(f"Got samples per channel...  {counter2}")
                    rx_time = datetime.now().strftime("%Y%m%d-%H%M%S")
                    np.save(f"rx_{rx_time}.npy", f1_i) #Channel 1
                    f0_i = np.zeros((rx_buffer_size.value), dtype=np.complex128)
                    f1_i = np.zeros((rx_buffer_size.value), dtype=np.complex128)
                    total_transferred = 0
                    number_of_samples_transferred = 0
                    print("End of data reached")
                #else:
                #    print("Unknown error")
            # Read the number of samples available in the card.
            spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_LEN, byref(available_user_databytes))
            
            # Check if there is sufficient data is available to read.
            if available_user_databytes.value >= rx_notify_size.value:
                
                # the data is available. We can read the data now. Get the data position in the card.
                spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_POS, byref(data_user_position))
                for bufferIndex in range(int(data_user_position.value),data_user_position.value+rx_notify_size.value):
                    counterX = self.num_channels.value * bufferIndex
                    f0_i[total_transferred+bufferIndex - 1] = np.complex_(float(rx_buffer[total_transferred+counterX - 1])
                    )  # Type is complex at the moment we can change it later
                    f1_i[total_transferred+bufferIndex - 1] = np.complex_(float(rx_buffer[total_transferred+counterX]))
                    counter += counterX
                    counter2 += bufferIndex
                spcm_dwSetParam_i32(self.card, SPC_DATA_AVAIL_CARD_LEN, rx_notify_size.value)
                # Count the number of samples. This is useful when we know how many samples are transferred from the Txcard.
                total_transferred += int((rx_notify_size.value)/4)
                number_of_samples_transferred += rx_notify_size.value/2
            spcm_dwGetParam_i64(self.card, SPC_TS_AVAIL_USER_LEN, byref(available_timestamp_bytes))
            
            if available_timestamp_bytes.value/16 >= 2:
                # Get the timestamp data position in the card.
                spcm_dwGetParam_i64(self.card, SPC_TS_AVAIL_USER_POS, byref(available_timestamp_postion))
                for i in range(0, int(available_timestamp_bytes.value / 16), 1):
                    lIndex = int(available_timestamp_postion.value / 8) + i * 2
                    #timestamp1          = timeStampBuffer[timeStampUserPos.value]  
                    #timestamp0          = timeStampBuffer[timeStampUserPos.value+16]
                    #timeStampDifference = timestamp1- timestamp0
                    timestampVal = ts_buffer[lIndex] / 10000000
                    #print(f"Calculated time       :        {timestampVal}")
                    #timestampVal = timeStampBuffer[1] / self.sample_rate
                    print(f"Calculated time       :        {timestampVal}")
                print(f"Got total samples...        {counter}")
                print(f"Got samples per channel...  {counter2}")
                rx_time = datetime.now().strftime("%Y%m%d-%H%M%S")
                np.save(f"rx_{rx_time}.npy", f1_i) #Channel 1
                f0_i = np.zeros((rx_buffer_size.value), dtype=np.complex128)
                f1_i = np.zeros((rx_buffer_size.value), dtype=np.complex128)
                #total_transferred = 0
                number_of_samples_transferred = 0
                print("End of data reached")
                #availableTimestamps     -= (2*16)
                #timeStampBuffpos     = cast(timeStampBuffer, c_void_p).value + (2*16)

                # Move memory: Current ring buffer position,
                # position in sequence data and amount to transfer (=> notify size)
                # ctypes.memmove(ring_buffer_position, timeStampBuffpos, 2*16)
 
                spcm_dwSetParam_i32(self.card,SPC_TS_AVAIL_CARD_LEN,available_timestamp_bytes)
    
                           
    def _FIFO_gated_mode_example(self):
        
        #Define rx buffer
        rx_data = np.empty(shape=(1, self.memory_size * self.num_channels.value), dtype=np.int16)
        rx_buffer = rx_data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        lNotifySize = int32(0)
        RxBufferSize = uint64(self.memory_size * 2 * self.num_channels.value)       #Todo make multiples of 4096 kB.  
        spcm_dwDefTransfer_i64(
            self.card, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, lNotifySize, rx_buffer, uint64(0), RxBufferSize
        )

        
        
        spcm_dwSetParam_i32(
            self.card, SPC_TIMEOUT, 10000
        )  # Todo: trigger timeout set to 10 seconds. Maybe make it variable?
        err = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER)
        self.handle_error(err)
        print("Card Started...")
        qwTotalMem = uint64(0)
        qwToTransfer = uint64(MEGA_B(16))
        lStatus = int32()
        lAvailUser = int32()
        lPCPos = int32()
        rxCounter = 0
        while not self.emergency_stop.is_set():
            # 
            spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
            #spcm_dwSetParam_i32 (self.card, SPC_TIMEOUT, 100)
            self.handle_error(err)
            spcm_dwGetParam_i32(self.card, SPC_M2STATUS, byref(lStatus))
            spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_LEN, byref(lAvailUser))
            spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_POS, byref(lPCPos))
            rxCounter += 1
            print("Rx Counter is: " + str(rxCounter)) 
            if lAvailUser.value >= lNotifySize.value:
                #print("Rx Counter is: " + str(rxCounter)) 
                qwTotalMem.value += lNotifySize.value
                sys.stdout.write(
                    "Stat:{0:08x} Pos:{1:08x} Avail:{2:08x} Total:{3:.2f}MB/{4:.2f}MB\n".format(
                        lStatus.value,
                        lPCPos.value,
                        lAvailUser.value,
                        c_double(qwTotalMem.value).value / MEGA_B(1),
                        c_double(qwToTransfer.value).value / MEGA_B(1),
                    )
                )
                f0_i = np.zeros((self.memory_size), dtype=np.complex128)
                f1_i = np.zeros((self.memory_size), dtype=np.complex128)
                offset0 = np.complex_(0.0)
                offset1 = np.complex_(0.0)
                counter = 0
                counter2 = 0
                for bufferIndex in range(int(lPCPos.value), self.memory_size):
                    counterX = self.num_channels.value * bufferIndex
                    f0_i[bufferIndex - 1] = np.complex_(
                        float(rx_buffer[counterX - 1])
                    )  # Type is complex at the moment we can change it later
                    f1_i[bufferIndex - 1] = np.complex_(float(rx_buffer[counterX]))
                    # offset0 += f0_i[bufferIndex]
                    # offset1 += f1_i[bufferIndex]
                    counter = counterX
                    counter2 = bufferIndex
                # Todo Scaling to mV..
                print(f"Got total samples...        {counter}")
                print(f"Got samples per channel...  {counter2}")
                rx_time = datetime.now().strftime("%Y%m%d-%H%M%S")
                # np.save("rx_channel_" + str(rxCounter+1)+ "_1.npy", f0_i) #Channel 2 #Berk Note fix
                np.save(f"rx_{rx_time}.npy", f1_i) #Channel 1
                #np.save(f"rx_debug.npy", f1_i)
                print("Done")
                spcm_dwSetParam_i32(self.card, SPC_DATA_AVAIL_CARD_LEN, lNotifySize.value)
                
                #err = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_START)
                
        # spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)
        self.handle_error(err)

    def _receiver_example(self):  # self note: Add type?
        # rx_buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))

        # Create Rx buffer pointer
        rx_data = np.empty(shape=(1, self.memory_size * self.num_channels.value), dtype=np.int16)
        rx_buffer = rx_data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        lNotifySize = int32(0)

        # Determine the size of the bufffer.
        RxBufferSize = uint64(self.memory_size * 2 * self.num_channels.value)

        # Set timeout for trigger

        spcm_dwDefTransfer_i64(
            self.card, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, lNotifySize, rx_buffer, uint64(0), RxBufferSize
        )
        # Define the DMA transfer

        spcm_dwSetParam_i32(
            self.card, SPC_TIMEOUT, 10000
        )  # Todo: trigger timeout set to 10 seconds. Maybe make it variable?

        # Start the card and wait for trigger. DMA flag is also enabled
        err = spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER)
        self.handle_error(err)
        print("Card Started...")
        print("Waiting for trigger...")
        if spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_WAITTRIGGER) == ERR_TIMEOUT:
            print("No trigger detected!! Then, trigger is forced now!..")
            spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_FORCETRIGGER)
        #
        # spcm_dwSetParam_i32 (self.card, SPC_TIMEOUT, 0)
        spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_CARD_WAITREADY)
        spcm_dwSetParam_i32(self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        self.handle_error(err)
        # print ("Card is stopped now and data we got the floowing data: ")
        # Transfer the data
        # print("Transfer finished! Post_processing received data...")

        f0_i = np.zeros((self.memory_size), dtype=np.complex128)
        f1_i = np.zeros((self.memory_size), dtype=np.complex128)
        offset0 = np.complex_(0.0)
        offset1 = np.complex_(0.0)
        counter = 0
        counter2 = 0
        for bufferIndex in range(1, self.memory_size):  # int(self.memory_size/self.num_channels.value)-1
            counterX = self.num_channels.value * bufferIndex
            f0_i[bufferIndex - 1] = np.complex_(
                float(rx_buffer[counterX - 1])
            )  # Type is complex at the moment we can change it later
            f1_i[bufferIndex - 1] = np.complex_(float(rx_buffer[counterX]))
            # offset0 += f0_i[bufferIndex]
            # offset1 += f1_i[bufferIndex]
            counter = counterX
            counter2 = bufferIndex
        # Todo Scaling to mV..
        print(f"Got total samples...        {counter}")
        print(f"Got samples per channel...  {counter2}")
        # with open (r'test.txt','a') as fp:
        #     for index1, index2 in zip(range(len(f0_i)),range(len(f1_i))):
        #     # write each item on a new line
        #         fp.write(str(f0_i[index1]) + " " + str(f1_i[index2])+ "\n")
        np.save("rx_channel_1.npy", f0_i)
        np.save("rx_channel_2.npy", f1_i)
        print("Done")
        # Post Processing.. To be discussed
        # offset0 /= float(self.memory_size)
        # offset1 /= float(self.memory_size)
        print("Finished!...")

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
