'''
@ Short descp: Spectrum cards 2 m4i_6622-x8 spectrum cards sync test with star-Hub python implementation with GUI
@ Author: Berk Silemek
@ Last modification: 02.12.2019
'''

import sys
import matplotlib
matplotlib.use("TkAgg")
matplotlib.rcParams['agg.path.chunksize'] = 10000
#from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk) #try the line below if error occurs
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
import numpy as np
from Tkinter import *
print('matplotlib: {}'.format(matplotlib.__version__))
#from tkMessageBox import *
from pyspcm import *
from spcm_tools import *
import math
import ctypes

#from tkinter import ttk
#import gc


from matplotlib import pyplot as plt
class MainClass:
   def __init__(self,master):
       self.master = master
       self.fsamp  = 625e6
       #global returnPulse
   def StartGui(self,master):
       self.v = IntVar(master=master)
       self.v.set(2)
       def sendCommands():
           self.pulseLength                 = float(self.e1.get())
           self.waitLength                  = float(self.e4.get())   
           self.loopNum                     = int(self.e2.get())
           self.AmplitudeSetting            = int(self.e3.get())
           self.SegmentSizeSetting          = int(self.e5.get())
           self.DigitalAmplitudeSetting     = int(self.e6.get())
           self.fsamp                       = float(self.e9.get())
           self.fbas                        = float(self.e8.get())
           self.NsamplePulse                = int((float(self.pulseLength)/(1.0/self.fsamp)))
           self.NsampleWait                 = int((float(self.waitLength)/(1.0/self.fsamp)))
           self.SegmentSizePulse            = uint64(self.NsamplePulse)           
           self.SegmentSizeWait             = uint64(self.NsampleWait)
           self.MemsizeWait                 = uint64(self.NsampleWait*4*2)
           self.MemsizePulse                = uint64(self.NsamplePulse*4*2)
           self.intp2  		                = ctypes.POINTER(ctypes.c_int16)
           self.intp3  		                = ctypes.POINTER(ctypes.c_int16)
	   self.intp4  		                = ctypes.POINTER(ctypes.c_int16)
       f = plt.figure(figsize=(6,6), dpi=100)
       a = f.add_subplot(111)
       a.plot([1,2,3,4,5,6,7,8],[5,6,1,3,8,9,3,5])
       plt.xlabel("Time")
       plt.ylabel("Amplitude")
       #frame   = Frame(master)
       #frame.grid(row=0,column=0, sticky="n")
       canvas = FigureCanvasTkAgg(f, master)
       canvas.draw()
       #canvas.grid(row=0,column=1)

       canvas.get_tk_widget().grid(row=0, column=3,columnspan=3, rowspan=12,sticky=W+E+N+S)#, expand=True)
       toolbarFrame = Frame(master=master)
       toolbarFrame.grid(row=12,column=3)
       toolbar = NavigationToolbar2TkAgg(canvas, toolbarFrame)
       toolbar.update()
       def StartCard():
           if (self.InitVariables()):
               plt.clf()
               a = f.add_subplot(111)
               a.plot(self.t,self.returnPulse)
               plt.xlabel("Time")
               plt.ylabel("Amplitude")
               canvas.draw()
               self.m4iCommonSettings()
               if(self.v.get() == 1):
                   self.m4iNormalMode()
               elif(self.v.get() == 2):
                   self.m4isetSequenceMode()

               
       def startSequenceC():
            self.startSequence()
       def quitProgram():
           # if askyesno('Verify', 'Really quit?'):
            #    showwarning('Yes', 'Not yet implemented')
                master.quit()
                master.destroy()
                
           # else:
            #    showinfo('No', 'Quit has been cancelled')
       def ShowChoice():
           if (self.v.get() == 1):
               self.e1.config(state="disabled")
               self.e2.config(state="disabled")
               self.e5.config(state="disabled")
           elif(self.v.get()== 2):
               self.e1.config(state="normal")
               self.e2.config(state="normal")
               self.e5.config(state="normal")
       Radiobutton(master, text="Normal Mode", padx = 20, indicatoron = 0,variable=self.v,command=ShowChoice,value=1).grid(row = 7, column = 0, sticky = W, pady = 4)
       Radiobutton(master, text="Sequence Mode", padx = 20,indicatoron = 0,variable=self.v,command=ShowChoice,value=2).grid(row= 8, column = 0, sticky = W, pady = 4)
       Label(master, text = "Sample Pulse Length").grid      (row=1, column=0)
       Label(master, text = "Wait Time Length").grid         (row=2, column=0)
       Label(master, text = "Segment Size").grid             (row=9, column=0)
       Label(master, text = "Digital Amplitude Setting").grid(row=10, column=0)
       Label(master, text = "Sampling Frequency").grid       (row=12, column=0)
       Label(master, text = "Frequency").grid                (row=11, column=0)
       Label(master, text = "Loop Number").grid              (row=3, column=0)
       Label(master, text = "Amplitude").grid                (row = 4, column=0)
       Label(master, text = "Seconds").grid                  (row = 1, column=2)
       Label(master, text = "Seconds").grid                  (row = 3, column=2)       
       Label(master, text = "Seconds").grid                  (row = 2, column=2)
       Label(master, text = "0-1000").grid                   (row = 4, column=2)
       Label(master, text = "Step Size: 32").grid            (row = 9, column=2)
       Label(master, text = "Max: 32767").grid               (row = 10, column=2)
       Label(master, text = "Hz").grid                       (row = 12, column=2)
       Label(master, text = "Hz").grid                       (row = 11, column=2)
       self.e1 = Entry(master)
       self.e1.delete(0,END)
       self.e1.insert(0,"0.00001")
       self.e2 = Entry(master)
       self.e2.delete(0,END)
       self.e2.insert(0,"1")
       self.e3 = Entry(master)
       self.e3.delete(0,END)
       self.e3.insert(0,"1000")
       self.e4 = Entry(master)
       self.e4.delete(0,END)
       self.e4.insert(0,"0.00001")
       self.e1.grid(row=1, column=1)
       self.e2.grid(row=3, column=1)
       self.e3.grid(row=4, column=1)
       self.e4.grid(row=2, column=1)
       self.e5 = Entry(master)
       self.e5.grid(row=9, column=1)
       self.e5.delete(0,END)
       self.e5.insert(0,"128")
       self.e6 = Entry(master)
       self.e6.grid(row=10, column=1)
       self.e6.delete(0,END)
       self.e6.insert(0,"32767")
       self.e9 = Entry(master)
       self.e9.grid(row=11, column=1)
       self.e9.delete(0,END)
       self.e9.insert(0,"625000000")
       self.e8 = Entry(master)
       self.e8.grid(row=12, column=1)
       self.e8.delete(0,END)
       self.e8.insert(0,"125000000")
       Button(master, text = "Send Commands",      command=sendCommands).grid(row                   = 6, column = 0, sticky = W, pady = 4)
       Button(master, text = "Quit Program" ,      command=quitProgram).grid(row                    = 6, column = 1, sticky = W, pady = 4)
       Button(master, text = "Prepare Sequence" ,  command=StartCard).grid(row                      = 6, column = 2, sticky = W, pady = 4)
       Button(master, text = "Start Sequence"  ,   command=startSequenceC,padx = 20).grid(row       = 7, column = 2, sticky = E, pady = 1)
       #Spinbox(master, increment = (1/(self.fsamp))*32,textvariable="0.001",from_=0, to=0.1).grid(row               = 0, column = 0, pady = 4 ) 
        #modeButton = Button(master, text = "Mode: Sequence Mode",command=modeNormal).grid(row           = 5, column = 0)
       mainloop()
   def tukeywin(self,window_length, alpha=0.5):
    '''The Tukey window, also known as the tapered cosine window, can be regarded as a cosine lobe of width \alpha * N / 2
    that is convolved with a rectangle window of width (1 - \alpha / 2). At \alpha = 1 it becomes rectangular, and
    at \alpha = 0 it becomes a Hann window.
 
    We use the same reference as MATLAB to provide the same results in case users compare a MATLAB output to this function
    output
 
    Reference
    ---------
    http://www.mathworks.com/access/helpdesk/help/toolbox/signal/tukeywin.html
 
    '''
    # Special cases
    if alpha <= 0:
        return np.ones(window_length) #rectangular window
    elif alpha >= 1:
        return np.hanning(window_length)
 
    # Normal case
    x = np.linspace(0, 1, window_length)
    w = np.ones(x.shape)
 
    # first condition 0 <= x < alpha/2
    first_condition = x<alpha/2
    w[first_condition] = 0.5 * (1 + np.cos(2*np.pi/alpha * (x[first_condition] - alpha/2) ))
 
    # second condition already taken care of
 
    # third condition 1 - alpha / 2 <= x <= 1
    third_condition = x>=(1 - alpha/2)
    w[third_condition] = 0.5 * (1 + np.cos(2*np.pi/alpha * (x[third_condition] - 1 + alpha/2))) 
 
    return w

   def InitVariables(self):
       self.amp0   = self.DigitalAmplitudeSetting                #Orig 32000, Changed because signed integers for 16 bits can be upto 32768...Not So critical. 
       residual    = self.NsamplePulse%32
       residual2    = self.NsampleWait%32

       #print(residual,self.NsamplePulse,self.SegmentSizePulse)
       if (residual < 16):
           self.pulseLength = self.pulseLength - (residual*(1/self.fsamp))
       else:
           self.pulseLength = self.pulseLength + ((32-residual)*(1/self.fsamp))
       self.NsamplePulse                = int((float(self.pulseLength)/(1.0/self.fsamp)))
       if (residual2 < 16):
           self.waitLength = self.waitLength - (residual2*(1/self.fsamp))
       else:
           self.waitLength = self.waitLength + ((32-residual2)*(1/self.fsamp))
       self.NsampleWait                = int((float(self.waitLength)/(1.0/self.fsamp)))
       #print(self.NsamplePulse%32,self.NsamplePulse,self.SegmentSizePulse)
       if (not((self.NsamplePulse)%32 == 0.0)):
           print("Segmentation Error!")
       else:
           self.NsampleWait                 = int((float(self.waitLength)/(1.0/self.fsamp)))
           self.SegmentSizePulse            = uint64(self.NsamplePulse)           
           self.SegmentSizeWait             = uint64(self.NsampleWait)
           self.MemsizeWait                 = uint64(self.NsampleWait*4*2)
           self.MemsizePulse                = uint64(self.NsamplePulse*4*2)
           self.PI           = np.pi
           self.phi          = np.array(np.zeros(8)    , dtype = ctypes.c_double)    
           self.phiC         = np.array(np.zeros(8)    , dtype = ctypes.c_double)   #For Phase Calibration
           self.amp          = np.array(np.zeros(8)    , dtype = ctypes.c_double)
           self.ampC         = np.array(np.zeros(8)    , dtype = ctypes.c_double)  #For Amplitude Calibration
           self.k            = np.arange(float(self.NsamplePulse))      
           self.t            = (self.k/self.fsamp)
           fsinc             = 900e3
           sinct             = self.t+self.t[int(len(self.t)/2)-1]
           cdf               = 1.0*self.amp0*np.sin(2.0*np.pi*self.fbas*self.t)
           env               = 1.0*self.amp0*np.sinc(2.0*np.pi*fsinc*sinct)
           self.returnPulse = (cdf+env)*self.tukeywin(self.NsamplePulse,1)
           #Uncomment
           self.lStep        = uint32(0)
           self.llNext       = uint32(0)
           self.llLoop       = uint32(0)
           self.llValue      = uint64(0)
           
           self.phiC[0]      =  0.0           
           self.phiC[1]      = ((-6.4466583728790283)  * (np.pi / 180.0))
           self.phiC[2]      = ((-7.0045896053314207)  * (np.pi / 180.0))
           self.phiC[3]      = ((1.0142267853021623)   * (np.pi / 180.0))
           self.phiC[4]      = ((24.745329284667967)   * (np.pi / 180.0))
           self.phiC[5]      = ((16.720711231231689)   * (np.pi / 180.0))
           self.phiC[6]      = ((10.251145744323731)   * (np.pi / 180.0))
           self.phiC[7]      = ((8.3969257831573483)   * (np.pi / 180.0))
           
           self.ampC[0]      =  (1.0/1.0)
           self.ampC[1]      =  (1.0/1.0016713)
           self.ampC[2]      =  (1.0/1.00178224)
           self.ampC[3]      =  (1.0/0.97487734)
           self.ampC[4]      =  (1.0/0.97924877)
           self.ampC[5]      =  (1.0/1.068606)
           self.ampC[6]      =  (1.0/1.023)
           self.ampC[7]      =  (1.0/0.92414583)
           self.ampC.fill(1.0)
           self.phiC.fill(0.0)

           
           self.szErrorTextBuffer = create_string_buffer (ERRORTEXTLEN)
           self.b                 = np.array(np.zeros(self.NsamplePulse*4)   , dtype = ctypes.c_int16)
           self.c                 = self.b.reshape(4,self.NsamplePulse)
           self.d                 = np.reshape((self.c[0,:],self.c[1,:],self.c[2,:],self.c[3,:]),self.NsamplePulse*4,order='F')

           self.hCard             = spcm_hOpen (create_string_buffer(b'/dev/spcm1'))       
           self.hCard1            = spcm_hOpen (create_string_buffer(b'/dev/spcm2'))
           self.hSync             = spcm_hOpen (create_string_buffer(b'sync0'))
           #Uncomment
           return True
           #Current Configuration (24.01.2019)
           #spcm0: ADC card m4i_44
           #spcm1: Tx card1 m4i_66
           #spcm2: Tx card2 m4i_66
           #sync0: star-Hub
   def m4iCommonSettings(self):
       if(self.hCard == None):
           sys.stdout.write("Card0 is not Found")
           exit()
       elif(self.hCard1 == None):
           sys.stdout.write("Card1 is not Found")
           exit()
       elif(self.hSync == None):
         sys.stdout.write("Sync is not Found")
         exit()


        # Config, for TX card
       spcm_dwSetParam_i64 (self.hCard,  SPC_M2CMD,M2CMD_CARD_RESET)
       spcm_dwSetParam_i64 (self.hCard1, SPC_M2CMD,M2CMD_CARD_RESET)
       spcm_dwSetParam_i32 (self.hSync,  SPC_SYNC_ENABLEMASK, 0x0003)
       spcm_dwSetParam_i32 (self.hCard,  SPC_TRIG_ORMASK, SPC_TM_NONE)
       spcm_dwSetParam_i32 (self.hCard1, SPC_CLOCKMODE, SPC_CM_INTPLL)
       spcm_dwSetParam_i64 (self.hCard1, SPC_SAMPLERATE,int(self.fsamp))
       spcm_dwSetParam_i32 (self.hCard1, SPC_CLOCKOUT,  1) # enable clock output
       spcm_dwSetParam_i64 (self.hCard,  SPC_SAMPLERATE,int(self.fsamp))
       spcm_dwSetParam_i32 (self.hCard,  SPCM_X2_MODE, SPCM_XMODE_TRIGOUT)
       spcm_dwSetParam_i32 (self.hCard1, SPCM_X2_MODE, SPCM_XMODE_TRIGOUT)
       ##Enable First Cards Channels
       spcm_dwSetParam_i32 (self.hCard,  SPC_CHENABLE, CHANNEL0|CHANNEL1|CHANNEL2|CHANNEL3)
       spcm_dwSetParam_i32 (self.hCard,  SPC_ENABLEOUT0, 1)
       spcm_dwSetParam_i32 (self.hCard,  SPC_AMP0, self.AmplitudeSetting)
       spcm_dwSetParam_i32 (self.hCard,  SPC_FILTER0, 0)
       #
       spcm_dwSetParam_i32 (self.hCard,  SPC_ENABLEOUT1, 1)
       spcm_dwSetParam_i32 (self.hCard,  SPC_AMP1, self.AmplitudeSetting)
       spcm_dwSetParam_i32 (self.hCard,  SPC_FILTER1, 0)
       #
       spcm_dwSetParam_i32 (self.hCard,  SPC_ENABLEOUT2, 1)
       spcm_dwSetParam_i32 (self.hCard,  SPC_AMP2, self.AmplitudeSetting)
       spcm_dwSetParam_i32 (self.hCard,  SPC_FILTER2, 0)
       #
       spcm_dwSetParam_i32 (self.hCard,  SPC_ENABLEOUT3, 1)
       spcm_dwSetParam_i32 (self.hCard,  SPC_AMP3, self.AmplitudeSetting)
       spcm_dwSetParam_i32 (self.hCard,  SPC_FILTER3, 0)
       #Enable Second Cards Channels
       spcm_dwSetParam_i32 (self.hCard1, SPC_CHENABLE, CHANNEL0|CHANNEL1|CHANNEL2|CHANNEL3)
       spcm_dwSetParam_i32 (self.hCard1, SPC_ENABLEOUT0, 1)
       spcm_dwSetParam_i32 (self.hCard1, SPC_AMP0, self.AmplitudeSetting)
       spcm_dwSetParam_i32 (self.hCard1, SPC_FILTER0, 0)
       #
       spcm_dwSetParam_i32 (self.hCard1, SPC_ENABLEOUT1, 1)
       spcm_dwSetParam_i32 (self.hCard1, SPC_AMP1, self.AmplitudeSetting)
       spcm_dwSetParam_i32 (self.hCard1, SPC_FILTER1, 0)
       #
       spcm_dwSetParam_i32 (self.hCard1, SPC_ENABLEOUT2, 1)
       spcm_dwSetParam_i32 (self.hCard1, SPC_AMP2, self.AmplitudeSetting)
       spcm_dwSetParam_i32 (self.hCard1, SPC_FILTER2, 0)
       #
       spcm_dwSetParam_i32 (self.hCard1, SPC_ENABLEOUT3, 1)
       spcm_dwSetParam_i32 (self.hCard1, SPC_AMP3, self.AmplitudeSetting)
       spcm_dwSetParam_i32 (self.hCard1, SPC_FILTER3, 0)
   def m4iNormalMode(self):
       # single pulse looped "loopNum" times
    spcm_dwSetParam_i32 (self.hCard,  SPC_CARDMODE, SPC_REP_STD_SINGLE)
    spcm_dwSetParam_i32 (self.hCard,  SPC_MEMSIZE ,self.MemsizePulse)
    spcm_dwSetParam_i32 (self.hCard,  SPC_LOOPS   , self.loopNum)
    
    spcm_dwSetParam_i32 (self.hCard1, SPC_CARDMODE, SPC_REP_STD_SINGLE)
    spcm_dwSetParam_i32 (self.hCard1, SPC_MEMSIZE ,self.MemsizePulse)
    spcm_dwSetParam_i32 (self.hCard1, SPC_LOOPS   , self.loopNum)
    self.NormalModeDataPrep()
    self.err_reg = uint32(0)
    self.err_val = int32(0)
    self.dwError3 = spcm_dwSetParam_i32 (self.hSync,  SPC_M2CMD, M2CMD_CARD_START    | M2CMD_CARD_FORCETRIGGER | M2CMD_CARD_WAITREADY)
    if(self.dwError3 != 0): 
        spcm_dwGetErrorInfo_i32 (self.hCard, byref(self.err_reg), byref(self.err_val), self.szErrorTextBuffer)
        print("CARD-1")
        sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
        sys.stdout.write("{0}\n".format(self.err_reg.value))
        sys.stdout.write("{0}\n".format(self.err_val.value))
   def m4isetSequenceMode (self):
    #Uncomment for Normal Operation
    #Set repetation and Triggers for Card 1, second and third line are for the sequence mode only
    spcm_dwSetParam_i32 (self.hCard,  SPC_CARDMODE,  SPC_REP_STD_SEQUENCE)    # Normal Mode : SPC_REP_STD_SINGLE , Sequence Mode: SPC_REP_STD_SEQUENCE
    spcm_dwSetParam_i32 (self.hCard,  SPC_SEQMODE_MAXSEGMENTS,    self.SegmentSizeSetting)                     
    spcm_dwSetParam_i32 (self.hCard,  SPC_SEQMODE_STARTSTEP,      0)                       # Start from the first segment
    spcm_dwSetParam_i32 (self.hCard1, SPC_CARDMODE, SPC_REP_STD_SEQUENCE)    # Normal Mode : SPC_REP_STD_SINGLE , Sequence Mode: SPC_REP_STD_SEQUENCE
    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_MAXSEGMENTS,    self.SegmentSizeSetting)                     # Two memory parts are used
    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_STARTSTEP,      0)                       # Start from the first segment
    #Uncomment For Normal Operation
    self.tMatrix(self.pulseLength,self.waitLength)
    
    
    
    # start the sequence written to cards
   def startSequence(self):
    self.err_reg  = uint32(0)
    self.err_val  = int32(0)
    self.dwError3 = spcm_dwSetParam_i32 (self.hSync,  SPC_M2CMD, M2CMD_CARD_START    | M2CMD_CARD_FORCETRIGGER | M2CMD_CARD_WAITREADY)
    if(self.dwError3 != 0): 
      spcm_dwGetErrorInfo_i32 (self.hCard, byref(self.err_reg), byref(self.err_val), self.szErrorTextBuffer)
      print("CARD-1")
      sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
      sys.stdout.write("{0}\n".format(self.err_reg.value))
      sys.stdout.write("{0}\n".format(self.err_val.value))
    if(self.dwError3 != 0): 
      print("CARD-2")
      spcm_dwGetErrorInfo_i32 (self.hCard1, byref(self.err_reg), byref(self.err_val), self.szErrorTextBuffer)
      sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
      sys.stdout.write("{0}\n".format(self.err_reg.value))
      sys.stdout.write("{0}\n".format(self.err_val.value))
    if(self.dwError3 != 0):
       spcm_dwGetErrorInfo_i32 (self.hSync, byref(self.err_reg), byref(self.err_val), self.szErrorTextBuffer)
       print("ERROR HSYNC CARD")
       sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
       sys.stdout.write("{0}\n".format(self.err_reg.value))
       sys.stdout.write("{0}\n".format(self.err_val.value))
       spcm_vClose (self.hSync)
       exit ()
       
       
       
       
       
    print('Reached to End of Code')
    spcm_vClose (self.hCard)
    spcm_vClose (self.hCard1)
    spcm_vClose (self.hSync)
    
    # sequence:
   def tMatrix(self,tpulse,tWait): #The time unit is seconds
      fsinc             = 900e3
      sinct             = self.t+self.t[int(len(self.t)/2)-1]
      env               = 1.0*np.sinc(2.0*np.pi*fsinc*sinct)
      
      # 
      self.segmentCount  = 0
      self.segmentCount1 = 1
      self.segmentCount2 = 2
      self.n = 8
      self.txSignal0  = np.sin(2.0*np.pi*self.fbas*self.t)
      self.txSignal90 = np.sin(2.0*np.pi*self.fbas*self.t+self.PI/2.0)
      for i in range(self.n):
        for j in range(self.n):
            self.amp.fill(0.0)
            self.phi.fill(0.0)
            if(j>i):
                self.amp[i] =    1.0*self.ampC[i]
                self.amp[j] =    1.0*self.ampC[j]
                
                
                
                
                
                # Routine to transfer one segment to the card
                
                # 4 channel pulses, important is int16, for low field only one might be required
                self.c[0,:] =    np.int16(self.amp0*self.amp[3]*((env+self.txSignal0)*(self.tukeywin(self.NsamplePulse,1))))
                self.c[1,:] =    np.int16(self.amp0*self.amp[2]*((env+self.txSignal0)*(self.tukeywin(self.NsamplePulse,1))))
                self.c[2,:] =    np.int16(self.amp0*self.amp[1]*((env+self.txSignal0)*(self.tukeywin(self.NsamplePulse,1))))
                self.c[3,:] =    np.int16(self.amp0*self.amp[0]*((env+self.txSignal0)*(self.tukeywin(self.NsamplePulse,1))))
                self.d      =    np.reshape((self.c[3,:],self.c[2,:],self.c[1,:],self.c[0,:]),self.NsamplePulse*4,order='F')
                # pointer:
                self.n12  	= self.d.ctypes.data_as(self.intp2)
                # write segment count -> identifier for a segment
                spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount)                      # We are configuring the segment 0    
                # write size of the segment
                spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizePulse)
                # transfer the actual segment
                spcm_dwDefTransfer_i64 (self.hCard,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizePulse))
                dwError1 = spcm_dwSetParam_i32 (self.hCard,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                if(dwError1 != 0):
                    spcm_dwGetErrorInfo_i32 (self.hCard, None, None, self.szErrorTextBuffer)
                    print("Card 1- ERROR in Segment 1")
                    sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
                    spcm_vClose (self.hCard)
                    exit ()
                #Setting up the sequence memory 
                self.lStep         = self.segmentCount                         # current step is segmentCount
                self.llSegment     = self.segmentCount                         # associated with memory
                self.llLoop        = self.loopNum                                # Pattern will be repeated 10 times
                self.llNext        = self.segmentCount1                       # Next step is Step#1
                self.llCondition   = SPCSEQ_ENDLOOPALWAYS                # Unconditionally leave current step
                # combine all the parameters to one int64 bit value
                self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                spcm_dwSetParam_i64 (self.hCard, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
                spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount1)                      # We are configuring the segment 0    
                spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizeWait)
                
                # end of writing the segment routine
                
                
                
                
                # waiting segment 
                self.d             = np.array(np.zeros(self.NsampleWait*4)    , dtype = ctypes.c_int16)
                self.n12  	       = self.d.ctypes.data_as(self.intp2)
                spcm_dwDefTransfer_i64 (self.hCard,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizeWait))
                self.dwError1      = spcm_dwSetParam_i32 (self.hCard,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                if(self.dwError1 != 0):
                    spcm_dwGetErrorInfo_i32 (self.hCard, None, None, self.szErrorTextBuffer)
                    print("Card 1- ERROR in Segment 1")
                    sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
                    spcm_vClose (self.hCard)
                    exit ()
                #Setting up the sequence memory 
                self.lStep                   = self.segmentCount1                         # current step is segmentCount
                self.llSegment               = self.segmentCount1                         # associated with memory
                self.llLoop                  = self.loopNum                                # Pattern will be repeated 10 times
                self.llNext                  = self.segmentCount2                       # Next step is Step#1
                self.llCondition             = SPCSEQ_ENDLOOPALWAYS                # Unconditionally leave current step
                # combine all the parameters to one int64 bit value
                self.llValue.value           = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                spcm_dwSetParam_i64 (self.hCard, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
                self.segmentCount            = self.segmentCount  + 2
                self.segmentCount1           = self.segmentCount1 + 2
                self.segmentCount2           = self.segmentCount2 + 2  
            else:
                self.amp[i]                  = 1.0*self.ampC[i]
                self.amp[j]                  = 1.0*self.ampC[j]
                self.phi[i]                  = 0.0+self.phiC[i]
                self.phi[j]                  = self.PI/2.0+self.phiC[j]
                self.c[0,:] =    np.int16(self.amp[3]*self.amp0*np.sin(2.0*np.pi*self.fbas*self.t+self.phi[3]))
                self.c[1,:] =    np.int16(self.amp[2]*self.amp0*np.sin(2.0*np.pi*self.fbas*self.t+self.phi[2]))
                self.c[2,:] =    np.int16(self.amp[1]*self.amp0*np.sin(2.0*np.pi*self.fbas*self.t+self.phi[1]))
                self.c[3,:] =    np.int16(self.amp[0]*self.amp0*np.sin(2.0*np.pi*self.fbas*self.t+self.phi[0]))  
                self.d = np.reshape((self.c[3,:],self.c[2,:],self.c[1,:],self.c[0,:]),self.NsamplePulse*4,order='F')
                self.n12  	= self.d.ctypes.data_as(self.intp2)
                if(not((i == self.n-1) and (j == self.n-1))):
                    spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount)
                    spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizePulse)
                    spcm_dwDefTransfer_i64 (self.hCard,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizePulse))
                    #print("Starting DMA Transfer for Segment 1 for CARD: 1")
                    spcm_dwSetParam_i32 (self.hCard,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                    #Setting up the sequence memory 
                    self.lStep        = self.segmentCount                         # current step is segmentCount
                    self.llSegment    = self.segmentCount                         # associated with memory
                    self.llLoop       = self.loopNum                            # Pattern will be repeated 10 times
                    self.llNext       = self.segmentCount1                      # Next step is Step#1
                    self.llCondition  = SPCSEQ_ENDLOOPALWAYS                # Unconditionally leave current step
                    # combine all the parameters to one int64 bit value
                    self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                    spcm_dwSetParam_i64 (self.hCard, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
                    #############################################################################################################
                    #for asss in range(len(d)):
                    #intp_1[asss] = int16(0)
                    spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount1)                      # We are configuring the segment 0    
                    spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizeWait)
                    self.d       = np.array(np.zeros(self.NsampleWait*4)    , dtype = ctypes.c_int16)
                    self.n12  	= self.d.ctypes.data_as(self.intp2)
                    spcm_dwDefTransfer_i64 (self.hCard,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizeWait))
                    self.dwError1 = spcm_dwSetParam_i32 (self.hCard,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                    if(self.dwError1 != 0):
                        spcm_dwGetErrorInfo_i32 (self.hCard, None, None, self.szErrorTextBuffer)
                        print("Card 1- ERROR in Segment 1")
                        sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
                        spcm_vClose (self.hCard)
                        exit ()
                    #Setting up the sequence memory 
                    self.lStep        = self.segmentCount1                         # current step is segmentCount
                    self.llSegment    = self.segmentCount1                         # associated with memory
                    self.llLoop       = self.loopNum                                # Pattern will be repeated 10 times
                    self.llNext       = self.segmentCount2                       # Next step is Step#1
                    self.llCondition  = SPCSEQ_ENDLOOPALWAYS                # Unconditionally leave current step
                    # combine all the parameters to one int64 bit value
                    self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                    spcm_dwSetParam_i64 (self.hCard, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
                    self.segmentCount            = self.segmentCount + 2 
                    self.segmentCount1           = self.segmentCount1 + 2
                    self.segmentCount2           = self.segmentCount2 + 2
                else:
                    spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount)
                    spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizePulse)
                    spcm_dwDefTransfer_i64 (self.hCard,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizePulse))
                    print("Last DMA Transfer for Card: 1")
                    spcm_dwSetParam_i32 (self.hCard,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                    self.lStep        = self.segmentCount                         # current step is segmentCount
                    self.llSegment    = self.segmentCount                         # associated with memory
                    self.llLoop       = self.loopNum                                 # Pattern will be repeated N times
                    self.llNext       = self.segmentCount1                        # Next step is Step#1
                    self.llCondition  = SPCSEQ_ENDLOOPALWAYS               # Unconditionally leave current step
                    # combine all the parameters to one int64 bit value
                    self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                    spcm_dwSetParam_i64 (self.hCard, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
                    spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount1)                      # We are configuring the segment 0    
                    spcm_dwSetParam_i32 (self.hCard, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizeWait)
                    self.d       = np.array(np.zeros(self.NsampleWait*4)    , dtype = ctypes.c_int16)
                    self.n12  	= self.d.ctypes.data_as(self.intp2)
                    spcm_dwDefTransfer_i64 (self.hCard,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizeWait))
                    dwError1 = spcm_dwSetParam_i32 (self.hCard,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                    if(dwError1 != 0):
                        spcm_dwGetErrorInfo_i32 (self.hCard, None, None, self.szErrorTextBuffer)
                        print("Card 1- ERROR in Segment 1")
                        sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
                        spcm_vClose (self.hCard)
                        exit ()
                    #Setting up the sequence memory 
                    self.lStep        = self.segmentCount1                         # current step is segmentCount
                    self.llSegment    = self.segmentCount1                         # associated with memory
                    self.llLoop       = self.loopNum                                # Pattern will be repeated 10 times
                    self.llNext       = 0                       # Next step is Step#1
                    self.llCondition  = SPCSEQ_END               # Unconditionally leave current step
                    # combine all the parameters to one int64 bit value
                    self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                    spcm_dwSetParam_i64 (self.hCard, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)

      self.segmentCount  = 0
      self.segmentCount1 = 1
      self.segmentCount2 = 2
      for i in range(self.n):
        for j in range(self.n):
            self.amp.fill(0.0)
            self.phi.fill(0.0)
            if(j>i):
                self.amp[i] = 1.0*self.ampC[i]
                self.amp[j] = 1.0*self.ampC[j]
                self.phi[i] = 0.0+self.phiC[i]
                self.phi[j] = 0.0+self.phiC[j]
                self.c[0,:] =    np.int16(self.amp[7]*self.txSignal0)
                self.c[1,:] =    np.int16(self.amp[6]*self.txSignal0)
                self.c[2,:] =    np.int16(self.amp[5]*self.txSignal0)
                self.c[3,:] =    np.int16(self.amp[4]*self.txSignal0) 
                self.d = np.reshape((self.c[3,:],self.c[2,:],self.c[1,:],self.c[0,:]),self.NsamplePulse*4,order='F')
                self.n12  	= self.d.ctypes.data_as(self.intp2)
                spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount)                      # We are configuring the segment N    
                spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizePulse)
                spcm_dwDefTransfer_i64 (self.hCard1,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizePulse))
                #print("Starting DMA Transfer for Segment 1 for CARD: 2")
                dwError2 = spcm_dwSetParam_i32 (self.hCard1,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                if(dwError2 != 0):
                    spcm_dwGetErrorInfo_i32 (hCard1, None, None, szErrorTextBuffer)
                    print("Card 2-ERROR in Segment 1")
                    sys.stdout.write("{0}\n".format(szErrorTextBuffer.value))
                    spcm_vClose (self.hCard1)
                    exit ()
                self.lStep        = self.segmentCount                         # current step is segmentCount
                self.llSegment    = self.segmentCount                         # associated with memory
                self.llLoop       = self.loopNum                              # Pattern will be repeated 10 times
                self.llNext       = self.segmentCount1                        # Next step is Step#1
                llCondition  = SPCSEQ_ENDLOOPALWAYS                           # Unconditionally leave current step
            # combine all the parameters to one int64 bit value
                self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                spcm_dwSetParam_i64 (self.hCard1, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
                spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount1)                      # We are configuring the segment N    
                spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizeWait)
                self.d       = np.array(np.zeros(self.NsampleWait*4)    , dtype = ctypes.c_int16)
                self.n12  	= self.d.ctypes.data_as(self.intp2)
                spcm_dwDefTransfer_i64 (self.hCard1,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizeWait))
                #print("Starting DMA Transfer for Segment 1 for CARD: 2")
                spcm_dwSetParam_i32 (self.hCard1,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                self.lStep        = self.segmentCount1                  # current step is segmentCount
                self.llSegment    = self.segmentCount1                  # associated with memory
                self.llLoop       = self.loopNum                        # Pattern will be repeated 10 times
                self.llNext       = self.segmentCount2                  # Next step is Step#1
                self.llCondition  = SPCSEQ_ENDLOOPALWAYS                # Unconditionally leave current step
                self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                spcm_dwSetParam_i64 (self.hCard1, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)  
                self.segmentCount            = self.segmentCount  + 2
                self.segmentCount1           = self.segmentCount1 + 2
                self.segmentCount2           = self.segmentCount2 + 2  
            else:
                self.amp[i] = 1.0*self.ampC[i]
                self.amp[j] = 1.0*self.ampC[j]
                self.phi[i] = 0.0+self.phiC[i]
                self.phi[j] = self.PI/2.0+self.phiC[j]
                self.c[0,:] =    np.int16(self.amp[7]*self.amp0*np.sin(2.0*np.pi*self.fbas*self.t+self.phi[7]))
                self.c[1,:] =    np.int16(self.amp[6]*self.amp0*np.sin(2.0*np.pi*self.fbas*self.t+self.phi[6]))
                self.c[2,:] =    np.int16(self.amp[5]*self.amp0*np.sin(2.0*np.pi*self.fbas*self.t+self.phi[5]))
                self.c[3,:] =    np.int16(self.amp[4]*self.amp0*np.sin(2.0*np.pi*self.fbas*self.t+self.phi[4]))
                returnPulse =    self.c[0,:]
                self.d = np.reshape((self.c[3,:],self.c[2,:],self.c[1,:],self.c[0,:]),self.NsamplePulse*4,order='F')
                self.n12  	= self.d.ctypes.data_as(self.intp2)
                if(not((i == self.n-1) and (j == self.n-1))):
                    #############################################################################################################
                    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount)                      # We are configuring the segment N    
                    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizePulse)
                    spcm_dwDefTransfer_i64 (self.hCard1,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizePulse))
                    #print("Starting DMA Transfer for Segment 1 for CARD: 2")
                    spcm_dwSetParam_i32 (self.hCard1,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                    self.lStep        = self.segmentCount                        # current step is segmentCount
                    self.llSegment    = self.segmentCount                        # associated with memory
                    self.llLoop       = self.loopNum                             # Pattern will be repeated 10 times
                    self.llNext       = self.segmentCount1                       # Next step is Step#1
                    self.llCondition  = SPCSEQ_ENDLOOPALWAYS                # Unconditionally leave current step
                    # combine all the parameters to one int64 bit value
                    self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                    spcm_dwSetParam_i64 (self.hCard1, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
                    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount1)                      # We are configuring the segment N    
                    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizeWait)
                    self.d      = np.array(np.zeros(self.NsampleWait*4)    , dtype = ctypes.c_int16)
                    self.n12  	= self.d.ctypes.data_as(self.intp2)
                    spcm_dwDefTransfer_i64 (self.hCard1,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizeWait))
                    #print("Starting DMA Transfer for Segment 1 for CARD: 2")
                    spcm_dwSetParam_i32 (self.hCard1,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                    self.lStep        = self.segmentCount1                        # current step is segmentCount
                    self.llSegment    = self.segmentCount1                        # associated with memory
                    self.llLoop       = self.loopNum                             # Pattern will be repeated 10 times
                    self.llNext       = self.segmentCount2                       # Next step is Step#1
                    self.llCondition  = SPCSEQ_ENDLOOPALWAYS                # Unconditionally leave current step
                    self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                    spcm_dwSetParam_i64 (self.hCard1, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
                    self.segmentCount            = self.segmentCount + 2 
                    self.segmentCount1           = self.segmentCount1 + 2
                    self.segmentCount2           = self.segmentCount2 + 2
                else:
                #############################################################################################################
                    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount)                         
                    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizePulse)
                    spcm_dwDefTransfer_i64 (self.hCard1,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizePulse))
                    print("Last DMA Transfer for Card: 2")
                    spcm_dwSetParam_i32 (self.hCard1,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                    self.lStep        = self.segmentCount                         # current step is segmentCount
                    self.llSegment    = self.segmentCount                         # associated with memory
                    self.llLoop       = self.loopNum                              # Pattern will be repeated 10 times
                    self.llNext       = self.segmentCount1                        # Next step is Step#1
                    self.llCondition  = SPCSEQ_ENDLOOPALWAYS                      # Unconditionally leave current step
                    # combine all the parameters to one int64 bit value
                    self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                    spcm_dwSetParam_i64 (self.hCard1, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
                    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_WRITESEGMENT,   self.segmentCount1)                      # We are configuring the segment N    
                    spcm_dwSetParam_i32 (self.hCard1, SPC_SEQMODE_SEGMENTSIZE,    self.SegmentSizeWait)
                    self.d       = np.array(np.zeros(self.NsampleWait*4)    , dtype = ctypes.c_int16)
                    self.n12  	= self.d.ctypes.data_as(self.intp2)
                    spcm_dwDefTransfer_i64 (self.hCard1,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizeWait))
                    #print("Starting DMA Transfer for Segment 1 for CARD: 2")
                    spcm_dwSetParam_i32 (self.hCard1,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
                    self.lStep        = self.segmentCount1                        # current step is segmentCount
                    self.llSegment    = self.segmentCount1                        # associated with memory
                    self.llLoop       = self.loopNum                              # Pattern will be repeated 10 times
                    self.llNext       = 0                                         # Next step is Step#1
                    self.llCondition  = SPCSEQ_END                                # Unconditionally leave current step
                    self.llValue.value = (self.llCondition << 32) | (self.llLoop << 32) | (self.llNext << 16) | (self.llSegment)
                    spcm_dwSetParam_i64 (self.hCard1, SPC_SEQMODE_STEPMEM0 + self.lStep, self.llValue)
      #del(self.d)
      #del(self.n12)
      #gc.collect()
      #file_object.close()
   def NormalModeDataPrep(self):
        fsinc             = 900e3
        sinct             = self.t+self.t[int(len(self.t)/2)-1]
        cdf               = np.sin (2.0*np.pi*self.fbas*self.t)
        env               = np.sinc(2.0*np.pi*fsinc*sinct)
        self.MemsizePulse                = uint64(self.NsamplePulse*8)
	self.amp.fill(1.0)
	self.phi.fill(0.0)
        self.returnPulse = (cdf+env)*self.tukeywin(self.NsamplePulse,1)
        self.c[0,:] =    np.int16(self.amp[3]*self.amp0*((np.sin(2.0*np.pi*self.fbas*self.t+self.phi[3]))+env)*(self.tukeywin(self.NsamplePulse,1)))
        self.c[1,:] =    np.int16(self.amp[2]*self.amp0*((np.sin(2.0*np.pi*self.fbas*self.t+self.phi[2]))+env)*(self.tukeywin(self.NsamplePulse,1)))
        self.c[2,:] =    np.int16(self.amp[1]*self.amp0*((np.sin(2.0*np.pi*self.fbas*self.t+self.phi[1]))+env)*(self.tukeywin(self.NsamplePulse,1)))
        self.c[3,:] =    np.int16(self.amp[0]*self.amp0*((np.sin(2.0*np.pi*self.fbas*self.t+self.phi[0]))+env)*(self.tukeywin(self.NsamplePulse,1)))
        self.d = np.reshape((self.c[3,:],self.c[2,:],self.c[1,:],self.c[0,:]),self.NsamplePulse*4,order='F')
        self.n12  	= self.d.ctypes.data_as(self.intp3)
        spcm_dwDefTransfer_i64 (self.hCard,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n12,  uint64 (0), (self.MemsizePulse))
        dwError1 = spcm_dwSetParam_i32 (self.hCard,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        if(dwError1 != 0):
            spcm_dwGetErrorInfo_i32 (self.hCard, None, None, self.szErrorTextBuffer)
            print("Card 1- ERROR in Segment 1")
            sys.stdout.write("{0}\n".format(self.szErrorTextBuffer.value))
            spcm_vClose (self.hCard)
            exit ()
        self.c[0,:] =    np.int16(self.amp[7]*self.amp0*((np.sin(2.0*np.pi*self.fbas*self.t+self.phi[7]))+env)*(self.tukeywin(self.NsamplePulse,1)))
        self.c[1,:] =    np.int16(self.amp[6]*self.amp0*((np.sin(2.0*np.pi*self.fbas*self.t+self.phi[6]))+env)*(self.tukeywin(self.NsamplePulse,1)))
        self.c[2,:] =    np.int16(self.amp[5]*self.amp0*((np.sin(2.0*np.pi*self.fbas*self.t+self.phi[5]))+env)*(self.tukeywin(self.NsamplePulse,1)))
        self.c[3,:] =    np.int16(self.amp[4]*self.amp0*((np.sin(2.0*np.pi*self.fbas*self.t+self.phi[4]))+env)*(self.tukeywin(self.NsamplePulse,1)))
        self.d = np.reshape((self.c[3,:],self.c[2,:],self.c[1,:],self.c[0,:]),self.NsamplePulse*4,order='F')
        self.n13  	= self.d.ctypes.data_as(self.intp4)
        
        # write the whole sequence at once
        spcm_dwDefTransfer_i64 (self.hCard1,  SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32 (0), self.n13,  uint64 (0), (self.MemsizePulse))
        dwError2 = spcm_dwSetParam_i32 (self.hCard1,  SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)
        if(dwError2 != 0):
                spcm_dwGetErrorInfo_i32 (hCard1, None, None, szErrorTextBuffer)
                print("Card 2-ERROR in Segment 1")
                sys.stdout.write("{0}\n".format(szErrorTextBuffer.value))
                spcm_vClose (self.hCard1)
                exit ()
master = Tk()
test = MainClass(master)
test.StartGui(master)

#def m4iset (pvData,pvData1,pvDataN,pvDataN1,pvWait,NsamplePulse,NsampleWait):
