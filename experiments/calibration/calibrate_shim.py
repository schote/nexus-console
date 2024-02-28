"""Spin-echo spectrum."""
# %%
import logging

import matplotlib.pyplot as plt
import numpy as np

from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.utilities.sequences.spectrometry import fid
from console.utilities.snr import signal_to_noise_ratio

    

# %%
# Create acquisition control instance
configuration = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.ERROR, file_log_level=logging.DEBUG)

# %%
# FID
seq = fid.constructor(
    rf_duration=200e-6,
    adc_duration=50e-3,
    dead_time=2e-3,
    flip_angle=np.pi/4
    # adc_duration=8e-3,
    # use_fid=False
)


# %%
# set range for shims

def grad_mTToMV(grad_strength):
    gpa_gain = acq.seq_provider.gpa_gain #V/a
    grad_eff = acq.seq_provider.grad_eff #T/m/a
    return np.divide(grad_strength,np.multiply(gpa_gain, grad_eff))

def run_fid(f0, shims):
    params = AcquisitionParameter(
        larmor_frequency=f_0,
        b1_scaling=3.4,
        decimation=1000,
        gradient_offset=Dimensions(x=shims[0], y=shims[1], z=shims[2]),)

    acq.set_sequence(parameter=params, sequence=seq)
    acq_data: AcquisitionData = acq.run()
    return acq_data
    
start_range  = 0.1  #initial step size in mT/m
end_range   = 0.001 #final step size in mT/m
num_dummies = 3

shims_current =  [0.0028,0.0777,-0.0346]
shims_current =  [0.0,0.0,0.0]


# %%
# Larmor frequency:
f_0 = 1964848.0

shim_range = start_range
shims_best = shims_current

shims_current_mv    = grad_mTToMV(shims_current)
for idx in range(num_dummies):
    dummy_data = run_fid(f_0, shims_current_mv)
    
data                = run_fid(f_0, shims_current_mv)
acq_data            = np.mean(data.raw, axis=0)[0].squeeze()
data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
amp_best            = np.max(np.abs(data_fft))

dwell_time  = data.dwell_time
time_scale  = np.arange(np.size(acq_data))*dwell_time
fft_freq    = np.fft.fftshift(np.fft.fftfreq(np.size(acq_data), dwell_time))

fig, ax = plt.subplots(1,2)
ax[0].plot(time_scale*1e3,np.abs(acq_data), label = 'Initial')
ax[0].set_xlabel("Time [ms]")
ax[0].set_ylabel("Amplitude [mV?]")
ax[1].plot(fft_freq*1e-3, np.abs(data_fft), label = 'Initial')
ax[1].set_xlabel("Frequency [kHz]")
ax[1].set_ylabel("Amplitude [a.u]")

amp_data = [amp_best,]

while(shim_range > end_range):
    print("Shim range: +/-%.4f mT/m"%(shim_range))
    #X gradient
    shims_current_mv    = grad_mTToMV((shims_best[0]+shim_range/2, shims_best[1],shims_best[2]))
    acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
    data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
    amp_1               = np.max(np.abs(data_fft))


    shims_current_mv    = grad_mTToMV((shims_best[0]-shim_range/2, shims_best[1],shims_best[2]))
    acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
    data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
    amp_2               = np.max(np.abs(data_fft))


    print("X: Best: %.2f, Amp1: %.2f, Amp2: %.2f"%(amp_best, amp_1,amp_2))
    if amp_1 > amp_2 and amp_1 > amp_best:
        amp_best = amp_1
        shims_best = (shims_best[0]+shim_range/2, shims_best[1],shims_best[2])
    elif amp_2 > amp_1 and amp_2 > amp_best:
        amp_best = amp_2
        shims_best = (shims_best[0]-shim_range/2, shims_best[1],shims_best[2])
    #Y gradient   
    shims_current_mv    = grad_mTToMV((shims_best[0], shims_best[1]+shim_range/2,shims_best[2]))
    acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
    data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
    amp_1               = np.max(np.abs(data_fft))

    shims_current_mv    = grad_mTToMV((shims_best[0], shims_best[1]-shim_range/2,shims_best[2]))
    acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
    data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
    amp_2               = np.max(np.abs(data_fft))

    print("Y: Best: %.2f, Amp1: %.2f, Amp2: %.2f"%(amp_best, amp_1,amp_2))
    if amp_1 > amp_2 and amp_1 > amp_best:
        amp_best = amp_1
        shims_best = (shims_best[0], shims_best[1]+shim_range/2,shims_best[2])
    elif amp_2 > amp_1 and amp_2 > amp_best:
        amp_best = amp_2
        shims_best = (shims_best[0], shims_best[1]-shim_range/2,shims_best[2])

    #Z gradient
    shims_current_mv    = grad_mTToMV((shims_best[0], shims_best[1],shims_best[2]+shim_range/2))
    acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
    data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
    amp_1               = np.max(np.abs(data_fft))

    shims_current_mv    = grad_mTToMV((shims_best[0], shims_best[1],shims_best[2]-shim_range/2))
    acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
    data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
    amp_2               = np.max(np.abs(data_fft))

    print("Z: Best: %.2f, Amp1: %.2f, Amp2: %.2f"%(amp_best, amp_1,amp_2))
    if amp_1 > amp_2 and amp_1 > amp_best:
        amp_best = amp_1
        shims_best = (shims_best[0], shims_best[1],shims_best[2]+shim_range/2)
    elif amp_2 > amp_1 and amp_2 > amp_best:
        amp_best = amp_2
        shims_best = (shims_best[0], shims_best[1],shims_best[2]-shim_range/2)
    print(shims_best)
    amp_data.append(amp_best)
    shim_range *= 0.75
    
    
# FFT
shims_current_mv    = grad_mTToMV((shims_best[0], shims_best[1],shims_best[2]-shim_range/2))
acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
amp_2               = np.max(np.abs(data_fft))


ax[0].plot(time_scale*1e3,np.abs(acq_data), label = 'Final')
ax[0].set_xlabel("Time [ms]")
ax[0].set_ylabel("Amplitude [mV?]")
ax[1].plot(fft_freq*1e-3, np.abs(data_fft), label = 'Final')
ax[1].set_xlabel("Frequency [kHz]")
ax[1].set_ylabel("Amplitude [a.u]")

ax[1].set_xlim((-5,5))

ax[0].legend()
ax[1].legend()

plt.figure()
plt.plot(amp_data)
plt.xlabel("Shim iteration")
plt.ylabel("Peak amplitude")


f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]

snr = signal_to_noise_ratio(data_fft, dwell_time=dwell_time)

# Add information to acquisition data
acq_data.add_info({
    "adc-indo": "FID , 50 ms readout",
    "true f0": f_0 - f_0_offset,
    "magnitude spectrum max": amp_best,
    "snr dB": snr,
})

print(f"Frequency offset [Hz]: {f_0_offset}\nNew frequency f0 [Hz]: {f_0 - f_0_offset}")
print(f"Frequency spectrum max.: {amp_best}")
print("Acquisition data shape: ", acq_data.raw.shape)
print("SNR [dB]: ", snr)

# time_scale = np.arange(data.size)*acq_data.dwell_time
# # Plot spectrum
# fig, ax = plt.subplots(1,2, figsize=(10, 5))
# ax[0].plot(time_scale*1e3, np.abs(data))
# ax[0].set_xlabel("Time [ms]")
# ax[0].set_ylabel("Signal [mV]")
# ax[1].plot(fft_freq, np.abs(data_fft))
# # ax.set_xlim([-20e3, 20e3])
# ax[1].set_ylim([0, max_spec * 1.05])
# ax[1].set_ylabel("Abs. FFT Spectrum [a.u.]")
# ax[1].set_xlabel("Frequency [Hz]")
# plt.show()

# %%
# Save acquisition data

# acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\Jana")
# acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\brain-slice")
#acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\in-vivo")
# %%
