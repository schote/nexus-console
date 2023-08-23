"""Implementation of receive card."""
from dataclasses import dataclass
import ctypes
import numpy as np
import threading
import time

from console.spcm_control.device_interface import SpectrumDevice
from console.spcm_control.spcm.pyspcm import *  # noqa # pylint: disable=unused-wildcard-import
from console.spcm_control.spcm.spcm_tools import *  # noqa # pylint: disable=unused-wildcard-import
from console.utilities.receiver_postProcessing import wind

@dataclass
class RxCard(SpectrumDevice):
    """Implementation of RX device."""

    path:               str
    channel_enable:     list[int]
    max_amplitude:      list[int]
    sample_rate:        int
    memory_size:        int
    loops:              int
    
    __name__: str = "RxCard"

    def __post_init__(self):
        super().__init__(self.path)
        self.num_channels       = int32(0)
        self.lCardType          = int32(0)
        self.lmemory_size       = int64(0)
        self.lpost_trigger      = int32(0) 
        self.ltrigger_delay     = int32(0)
        self.lx0_mode           = int32(0)
        
        
        self.worker: threading.Thread | None = None
        self.emergency_stop = threading.Event()
#    Maybe create channel enable/disable option for later 
    '''
    def channel_lookup(self, enableList: list):
        ChannelList     = [CHANNEL0,CHANNEL1,CHANNEL2,CHANNEL3]
        helper          = []
        EnabledChannels = [] 
        
        for i in range (len(enableList)):
            if(enableList[i] == 1):
                helper.append(ChannelList[i])
                EnabledChannels = EnabledChannels | ChannelList[i]
    '''  
    def setup_card(self):
        # Get the card type and reset card
        spcm_dwGetParam_i32(self.card, SPC_PCITYP      , byref (self.lCardType))
        spcm_dwSetParam_i64(self.card, SPC_M2CMD       , M2CMD_CARD_RESET) #Needed?

        #Setup channels
        #Input impdefance and voltage setting for channel0
        #spcm_dwSetParam_i32(self.card, SPC_CHENABLE    , CHANNEL0 | CHANNEL1 | CHANNEL2 | CHANNEL3) #Todo for all channels
        spcm_dwSetParam_i32(self.card, SPC_CHENABLE    , CHANNEL0 | CHANNEL1) #Todo for all channels
        spcm_dwSetParam_i32(self.card, SPC_50OHM0      , 0) #Todo make it variable or input impedance always 50 ohms?  
        spcm_dwSetParam_i32(self.card, SPC_AMP0        , self.max_amplitude[0])

        #Input impdefance and voltage setting for channel1
        spcm_dwSetParam_i32(self.card, SPC_50OHM1      , 0) #Todo make it variable or input impedance always 50 ohms?  
        spcm_dwSetParam_i32(self.card, SPC_AMP1        , self.max_amplitude[1])
        
        #Input impdefance and voltage setting for channel2
        # spcm_dwSetParam_i32(self.card, SPC_50OHM2      , 0) #Todo make it variable or input impedance always 50 ohms?  
        # spcm_dwSetParam_i32(self.card, SPC_AMP2        , self.max_amplitude[2])
        
        # #Input impdefance and voltage setting for channel3
        # spcm_dwSetParam_i32(self.card, SPC_50OHM3      , 0) #Todo make it variable or input impedance always 50 ohms?  
        # spcm_dwSetParam_i32(self.card, SPC_AMP3        , self.max_amplitude[3])
        
        # Get the number of active channels. This will be needed for handling the buffer size
        spcm_dwGetParam_i32(self.card, SPC_CHCOUNT     , byref(self.num_channels))
        print(f"Number of active Rx channels:           {self.num_channels.value}")
        
        # Some general cards settings 
        spcm_dwSetParam_i32(self.card, SPC_DIGITALBWFILTER , 0)#Digital filter setting for receiver
        spcm_dwSetParam_i32(self.card, SPC_CLOCKMODE   , SPC_CM_INTPLL) # Set clock mode
        spcm_dwSetParam_i32(self.card, SPC_CLOCKOUT    , 1)             # Output clock

        # Set card sampling rate in MHz
        spcm_dwSetParam_i64(self.card, SPC_SAMPLERATE  , MEGA(self.sample_rate))
        
        # Check actual sampling rate
        sample_rate = int64(0)
        spcm_dwGetParam_i64(self.card, SPC_SAMPLERATE  , byref(sample_rate))
        print(f"Rx device sampling rate:                {sample_rate.value*1e-6} MHz")
        if sample_rate.value != MEGA(self.sample_rate):
            raise Warning(
                f"Rx device sample rate                {sample_rate.value*1e-6} MHz does not match set sample rate of {self.sample_rate} MHz...")
        
        # Setup the card mode
        #self.post_trigger = self.memory_size - 8000 #Maybe make it variable? 
        self.post_trigger = 5000#(1/self.sample_rate)*8000 #Maybe make it variable? 
        self.pre_trigger  = 5000#(1/self.sample_rate)*8000 #Maybe make it variable? 
        # FIFO mode
        spcm_dwSetParam_i32 (self.card, SPC_CARDMODE    , SPC_REC_FIFO_GATE    )
        # Single mode
        #spcm_dwSetParam_i32 (self.card, SPC_CARDMODE    , SPC_REC_STD_SINGLE    )
        spcm_dwSetParam_i32 (self.card, SPC_MEMSIZE     , self.memory_size      )
        spcm_dwSetParam_i32 (self.card, SPC_POSTTRIGGER , self.post_trigger     )
        spcm_dwSetParam_i32 (self.card, SPC_PRETRIGGER ,  self.pre_trigger      )
        spcm_dwSetParam_i32 (self.card, SPC_LOOPS       , self.loops            )
        
        spcm_dwSetParam_i32 (self.card, SPC_TRIG_EXT1_MODE, SPC_TM_POS)
#        spcm_dwSetParam_i32 (self.card, SPC_TRIG_TERM, 1)     #If we use analog trigger
#        spcm_dwSetParam_i32 (self.card, SPC_TRIG_EXT0_LEVEL0, 1000)
        spcm_dwSetParam_i32 (self.card, SPC_TRIG_ORMASK, SPC_TMASK_EXT1)

        

        
        #spcm_dwGetParam_i32 (self.card, SPC_MEMSIZE     , byref(self.lmemory_size   )) # Read memory size
        spcm_dwGetParam_i32 (self.card, SPC_POSTTRIGGER , byref(self.lpost_trigger  )) # Read post trigger
        spcm_dwGetParam_i32 (self.card, SPC_TRIG_DELAY  , byref(self.ltrigger_delay )) # Trigger delay
        spcm_dwGetParam_i32 (self.card, SPCM_X1_MODE    , byref(self.lx0_mode       )) # X0_mode , Can be used as trigger.
        
        #print(f"Rx device memory size:                  {self.lmemory_size}"   )
        print(f"Post trigger time:                      {self.lpost_trigger}"  )   #todo calculate and write time units 
        print(f"Trigger delay is:                       {self.ltrigger_delay}" )   #todo calculate and write time units 
        print(f"X0 mode is:                             {self.lx0_mode}"       )  
        
        # Multi purpose I/O lines
        # spcm_dwSetParam_i32 (self.card, SPCM_X0_MODE, SPCM_XMODE_TRIGOUT) # X0 as gate signal, SPCM_XMODE_ASYNCOUT?
        # spcm_dwSetParam_i32 (self.card, SPCM_X1_MODE, SPCM_XMODE_DISABLE)
        # spcm_dwSetParam_i32 (self.card, SPCM_X2_MODE, SPCM_XMODE_DISABLE)
        # spcm_dwSetParam_i32 (self.card, SPCM_X3_MODE, SPCM_XMODE_DISABLE)

    def start_operation(self): #self note: Add type? 
        
        # event = threading.Event()
        self.emergency_stop.clear()
        self.worker = threading.Thread(target=self._FIFO_gated_mode_example)#, args=(None)) #
        self.worker.start()
        
        # Join after timeout of 10 seconds
        # worker.join()
        #event.set()
        #worker.join()
        # print("\nThread closed, stopping receiver card...")
        
        #print(rx_buffer.value)
        
    def stop_operation(self):
        if self.worker is not None:
            self.emergency_stop.set()
            self.worker.join()
            
            error = spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)
            self.handle_error(error)
            
            self.worker = None
        else:
            print("No active process found...")
        
    def _FIFO_gated_mode_example(self):
        # Read available memory first
        rx_data = np.empty(shape=(1, self.memory_size*self.num_channels.value), dtype=np.int16)
        rx_buffer = rx_data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        lNotifySize = int32 (0) 
        RxBufferSize = uint64(self.memory_size*2*self.num_channels.value) 


        
        spcm_dwDefTransfer_i64 (self.card, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, 
                                lNotifySize, rx_buffer, uint64 (0), RxBufferSize)
        
        spcm_dwSetParam_i32 (self.card, SPC_TIMEOUT, 25000) #Todo: trigger timeout set to 10 seconds. Maybe make it variable?
        err = spcm_dwSetParam_i32 (self.card, 
                                   SPC_M2CMD, 
                                   M2CMD_CARD_START | 
                                   M2CMD_CARD_ENABLETRIGGER)
        self.handle_error(err)
        print("Card Started...")
        qwTotalMem = uint64(0)
        qwToTransfer = uint64(MEGA_B(16))
        lStatus = int32()
        lAvailUser = int32()
        lPCPos = int32()
        rxCounter = 0
        while (not self.emergency_stop.is_set()):
            spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
            self.handle_error(err)
            spcm_dwGetParam_i32(self.card, SPC_M2STATUS,            byref(lStatus))
            spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_LEN, byref(lAvailUser))
            spcm_dwGetParam_i32(self.card, SPC_DATA_AVAIL_USER_POS, byref(lPCPos))
            
            if lAvailUser.value >= lNotifySize.value:
                qwTotalMem.value += lNotifySize.value
                sys.stdout.write("Stat:{0:08x} Pos:{1:08x} Avail:{2:08x} Total:{3:.2f}MB/{4:.2f}MB\n".format(lStatus.value, lPCPos.value, lAvailUser.value, c_double(qwTotalMem.value).value / MEGA_B(1), c_double(qwToTransfer.value).value / MEGA_B(1)))
                f0_i    = np.zeros((self.memory_size), dtype=np.complex128)
                f1_i    = np.zeros((self.memory_size), dtype=np.complex128)
                offset0 = np.complex_(0.0)
                offset1 = np.complex_(0.0)
                counter = 0
                counter2 = 0
                for bufferIndex in range(int(lPCPos.value),self.memory_size): 
                    counterX = self.num_channels.value*bufferIndex
                    f0_i[bufferIndex-1]   = np.complex_(float(rx_buffer[counterX-1])) #Type is complex at the moment we can change it later
                    f1_i[bufferIndex-1]   = np.complex_(float(rx_buffer[counterX]))
                    #offset0 += f0_i[bufferIndex]
                    #offset1 += f1_i[bufferIndex]
                    counter = counterX
                    counter2 = bufferIndex
                # Todo Scaling to mV.. 
                print(f"Got total samples...        {counter}")
                print(f"Got samples per channel...  {counter2}")
                np.save("rx_channel_" + str(rxCounter+1)+ "_1.npy", f0_i) #Channel 2 #Berk Note fix 
                np.save("rx_channel_" + str(rxCounter+1)+ "_2.npy", f1_i) #Channel 1
                rxCounter +=1 
                print('Done')
                spcm_dwSetParam_i32(self.card, SPC_DATA_AVAIL_CARD_LEN,  lNotifySize)
        #spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA)
        self.handle_error(err)
    def _receiver_example(self): #self note: Add type? 
        #rx_buffer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        
        # Create Rx buffer pointer 
        rx_data = np.empty(shape=(1, self.memory_size*self.num_channels.value), dtype=np.int16)
        rx_buffer = rx_data.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        lNotifySize = int32 (0) 
        
        # Determine the size of the bufffer. 
        RxBufferSize = uint64(self.memory_size*2*self.num_channels.value) 
       
        #Set timeout for trigger
        
        spcm_dwDefTransfer_i64 (self.card, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, 
                                lNotifySize, rx_buffer, uint64 (0), RxBufferSize)
        # Define the DMA transfer
        
        
        spcm_dwSetParam_i32 (self.card, SPC_TIMEOUT, 10000) #Todo: trigger timeout set to 10 seconds. Maybe make it variable?
        
        #Start the card and wait for trigger. DMA flag is also enabled
        err = spcm_dwSetParam_i32 (self.card, 
                                   SPC_M2CMD, 
                                   M2CMD_CARD_START | 
                                   M2CMD_CARD_ENABLETRIGGER)
        self.handle_error(err)
        print("Card Started...")
        print("Waiting for trigger...")
        if (spcm_dwSetParam_i32(self.card, SPC_M2CMD, 
                                M2CMD_CARD_WAITTRIGGER) == ERR_TIMEOUT):
            print("No trigger detected!! Then, trigger is forced now!..")
            spcm_dwSetParam_i32 (self.card, SPC_M2CMD, 
                                           M2CMD_CARD_FORCETRIGGER)
        #
        #spcm_dwSetParam_i32 (self.card, SPC_TIMEOUT, 0)
        spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_CARD_WAITREADY 
                                        )
        spcm_dwSetParam_i32 (self.card, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        self.handle_error(err)
        #print ("Card is stopped now and data we got the floowing data: ")
        #Transfer the data
        #print("Transfer finished! Post_processing received data...")

        f0_i    = np.zeros((self.memory_size), dtype=np.complex128)
        f1_i    = np.zeros((self.memory_size), dtype=np.complex128)
        offset0 = np.complex_(0.0)
        offset1 = np.complex_(0.0)
        counter = 0
        counter2 = 0
        for bufferIndex in range(1,self.memory_size): #int(self.memory_size/self.num_channels.value)-1
            counterX = self.num_channels.value*bufferIndex
            f0_i[bufferIndex-1]   = np.complex_(float(rx_buffer[counterX-1])) #Type is complex at the moment we can change it later
            f1_i[bufferIndex-1]   = np.complex_(float(rx_buffer[counterX]))
            #offset0 += f0_i[bufferIndex]
            #offset1 += f1_i[bufferIndex]
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
        print('Done')
        # Post Processing.. To be discussed
        #offset0 /= float(self.memory_size)
        #offset1 /= float(self.memory_size)
        print("Finished!...")
        
    def get_status(self):
        pass
