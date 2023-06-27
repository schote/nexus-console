#
# **************************************************************************
#
# simple_rec_single-cudafft.py                             (c) Spectrum GmbH
#
# **************************************************************************
#
# Example for all SpcMDrv based analog acquisition cards and a CUDA GPU. 
#
# Information about the different products and their drivers can be found
# online in the Knowledge Base:
# https://www.spectrum-instrumentation.com/en/platform-driver-and-series-differences
#
# Shows a simple Standard mode example using only the few necessary commands
#
# Feel free to use this source for own projects and modify it in any kind
#
# Documentation for the API as well as a detailed description of the hardware
# can be found in the manual for each device which can be found on our website:
# https://www.spectrum-instrumentation.com/en/downloads
#
# Further information can be found online in the Knowledge Base:
# https://www.spectrum-instrumentation.com/en/knowledge-base-overview
#
# **************************************************************************
#

import sys
import numpy as np
import cupy
import matplotlib.pyplot as plt

# import spectrum driver functions
from pyspcm import *
from spcm_tools import *


#
# **************************************************************************
# main 
# **************************************************************************
#

szErrorTextBuffer = create_string_buffer (ERRORTEXTLEN)
dwError = uint32 ();

# open card
hCard = spcm_hOpen (create_string_buffer (b'/dev/spcm0'))
if hCard == None:
    sys.stdout.write("no card found...\n")
    exit (1)


# read type, function and sn and check for A/D card
lCardType = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_PCITYP, byref (lCardType))
lSerialNumber = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_PCISERIALNO, byref (lSerialNumber))
lFncType = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_FNCTYPE, byref (lFncType))

sCardName = szTypeToName (lCardType.value)
if lFncType.value == SPCM_TYPE_AI:
    sys.stdout.write("Found: {0} sn {1:05d}\n".format(sCardName,lSerialNumber.value))
else:
    sys.stdout.write("This is an example for A/D cards.\nCard: {0} sn {1:05d} not supported by example\n".format(sCardName,lSerialNumber.value))
    spcm_vClose (hCard)
    exit (1) 

lNumCh = 1 # use only one channel for simplicity

# do a simple standard setup
lMemsize = int32(16384)
spcm_dwSetParam_i32 (hCard, SPC_CHENABLE,       (1 << lNumCh) - 1)      # enable the channel
spcm_dwSetParam_i32 (hCard, SPC_MEMSIZE,        lMemsize)               # acquire 16 kS in total
spcm_dwSetParam_i32 (hCard, SPC_POSTTRIGGER,    8192)                   # half of the total number of samples after trigger event
spcm_dwSetParam_i32 (hCard, SPC_CARDMODE,       SPC_REC_STD_SINGLE)     # single trigger standard mode
spcm_dwSetParam_i32 (hCard, SPC_TIMEOUT,        5000)                   # timeout 5 s
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ORMASK,    SPC_TMASK_SOFTWARE)     # trigger set to software
spcm_dwSetParam_i32 (hCard, SPC_TRIG_ANDMASK,   0)                      # ...
spcm_dwSetParam_i32 (hCard, SPC_CLOCKMODE,      SPC_CM_INTPLL)          # clock mode internal PLL
spcm_dwSetParam_i32 (hCard, SPC_CLOCKOUT,       0)                      # no clock output

lSetChannels = int32 (0)
spcm_dwGetParam_i32 (hCard, SPC_CHCOUNT,     byref (lSetChannels))      # get the number of activated channels

# setup the channels
lIR_mV = 1000
for lChannel in range (0, lSetChannels.value, 1):
    spcm_dwSetParam_i32 (hCard, SPC_AMP0 + lChannel * (SPC_AMP1 - SPC_AMP0),  int32 (lIR_mV)) # set input range to +/- 1000 mV

# we try to use the max samplerate
llMaxSamplerate = int64(0)
spcm_dwGetParam_i64 (hCard, SPC_MIINST_MAXADCLOCK, byref (llMaxSamplerate))
llSamplerate = llMaxSamplerate
spcm_dwSetParam_i64 (hCard, SPC_SAMPLERATE, llSamplerate)
sys.stdout.write ("Used samplerate: {0} MS/s\n".format(llSamplerate.value // 1000000))


# settings for the DMA buffer
qwBufferSize = uint64 (lMemsize.value * 2 * lSetChannels.value) # in bytes. Enough memory for all samples with 2 bytes each
lNotifySize = int32 (0) # driver should notify program after all data has been transfered


# define the page aligned numpy data buffer
pvBuffer = c_void_p ()
databuffer_unaligned = np.zeros([(4095 + qwBufferSize.value) // 2], dtype = np.int16)
databuffer_cpu =       databuffer_unaligned[((4096 - (databuffer_unaligned.__array_interface__['data'][0] & 0xfff)) // 2):]   # byte address but int16 sample: therefore / 2
pvBuffer =             databuffer_cpu.ctypes.data_as(c_void_p)  # Needed for the following code but using numpy-array (databuffer) directly is recommended.

spcm_dwDefTransfer_i64 (hCard, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, lNotifySize, pvBuffer, uint64 (0), qwBufferSize)

# start card and DMA
dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER | M2CMD_DATA_STARTDMA)

# check for error
if dwError != 0: # != ERR_OK
    spcm_dwGetErrorInfo_i32 (hCard, None, None, szErrorTextBuffer)
    sys.stdout.write("{0}\n".format(szErrorTextBuffer.value))
    spcm_vClose (hCard)
    exit (1)

# wait until data transfer has finished, then run a FFT on the GPU
else:
    dwError = spcm_dwSetParam_i32 (hCard, SPC_M2CMD, M2CMD_DATA_WAITDMA)
    if dwError != ERR_OK:
        if dwError == ERR_TIMEOUT:
            sys.stdout.write ("... Timeout\n")
        else:
            sys.stdout.write ("... Error: {0:d}\n".format(dwError))

    else:
        # this is the point to do anything with the data
        # e.g. calculate a FFT of the signal on a CUDA GPU
        sys.stdout.write ("Calculating FFT...\n")

        lMaxADCValue = int32()
        spcm_dwGetParam_i32 (hCard, SPC_MIINST_MAXADCVALUE, byref (lMaxADCValue))

        # number of threads in one CUDA block
        lNumThreadsPerBlock = 1024

        # copy data to GPU
        data_raw_gpu = cupy.array (databuffer_cpu)

        # convert raw data to volt
        CupyKernelConvertSignalToVolt = cupy.RawKernel(r'''
            extern "C" __global__
            void CudaKernelScale (const short* anSource, float* afDest, double dFactor) {
                int i = blockDim.x * blockIdx.x + threadIdx.x;
                afDest[i] = ((float)anSource[i]) * dFactor;
            }
            ''', 'CudaKernelScale')
        data_volt_gpu = cupy.zeros(lMemsize.value, dtype = cupy.float32)
        CupyKernelConvertSignalToVolt((lMemsize.value // lNumThreadsPerBlock,), (lNumThreadsPerBlock,), (data_raw_gpu, data_volt_gpu, (lIR_mV / 1000) / lMaxADCValue.value))

        # calculate the FFT
        fftdata_gpu = cupy.fft.fft (data_volt_gpu)

        # length of FFT result
        lNumFFTSamples = lMemsize.value // 2 + 1

        # scale the FFT result
        CupyKernelScaleFFTResult = cupy.RawKernel(r'''
            extern "C" __global__
            void CudaScaleFFTResult (complex<float>* pcompDest, const complex<float>* pcompSource, int lLen) {
                int i = blockDim.x * blockIdx.x + threadIdx.x;
                pcompDest[i].real (pcompSource[i].real() / (lLen / 2 + 1)); // divide by length of signal
                pcompDest[i].imag (pcompSource[i].imag() / (lLen / 2 + 1)); // divide by length of signal
            }
            ''', 'CudaScaleFFTResult', translate_cucomplex=True)
        CupyKernelScaleFFTResult((lMemsize.value // lNumThreadsPerBlock,), (lNumThreadsPerBlock,), (fftdata_gpu, fftdata_gpu, lMemsize.value))

        # calculate real spectrum from complex FFT result
        CupyKernelFFTToSpectrum = cupy.RawKernel(r'''
            extern "C" __global__
            void CudaKernelFFTToSpectrum (const complex<float>* pcompSource, float* pfDest) {
                int i = blockDim.x * blockIdx.x + threadIdx.x;
                pfDest[i] = sqrt (pcompSource[i].real() * pcompSource[i].real() + pcompSource[i].imag() * pcompSource[i].imag());
            }
            ''', 'CudaKernelFFTToSpectrum', translate_cucomplex=True)
        spectrum_gpu = cupy.zeros(lNumFFTSamples, dtype = cupy.float32)
        CupyKernelFFTToSpectrum ((lNumFFTSamples // lNumThreadsPerBlock,), (lNumThreadsPerBlock,), (fftdata_gpu, spectrum_gpu))

        # convert to dBFS
        CupyKernelSpectrumToDBFS = cupy.RawKernel(r'''
        extern "C" __global__
        void CudaKernelToDBFS (float* pfDest, const float* pfSource, int lIR_V) {
            int i = blockDim.x * blockIdx.x + threadIdx.x;
            pfDest[i] = 20. * log10f (pfSource[i] / lIR_V);
        }
        ''', 'CudaKernelToDBFS')
        CupyKernelSpectrumToDBFS((lNumFFTSamples // lNumThreadsPerBlock,), (lNumThreadsPerBlock,), (spectrum_gpu, spectrum_gpu, 1))

        spectrum_cpu = cupy.asnumpy (spectrum_gpu) # copy FFT spectrum back to CPU
        sys.stdout.write ("done\n")

        # plot FFT spectrum
        fStep = (llSamplerate.value // 2) / (spectrum_cpu.size - 1)
        afFreq = np.arange(0, llSamplerate.value // 2, fStep)
        plt.ylim([-140, 0]) # range of Y axis
        plt.plot(afFreq, spectrum_cpu[:(spectrum_cpu.size - 1)])
        plt.show()

# clean up
spcm_vClose (hCard)

