"""
B0 shimming implemention based on itterative shim offsets.

TODO:implement TR control, currently not needed since starting pulse sequence takes >1 second.
TODO:With each new best set F0 to frequency of maximum.
TODO:Clean code in while loop, single function to run the +/- range for all 3 gradients
"""
# %%
import logging

import matplotlib.pyplot as plt
import numpy as np

import console.spcm_control.globals as glob
from console.interfaces.interface_acquisition_data import AcquisitionData
from console.interfaces.interface_acquisition_parameter import Dimensions
from console.spcm_control.acquisition_control import AcquisitionControl
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
    adc_duration=100e-3,
    dead_time=3e-3,
    flip_angle=np.pi/4 #running with 45 degree to avoid overtipping.
    )


# %%
# set range for shims

def grad_mt_to_mv(grad_strength):
    """Translate gradient strength in mT per Meter to a mv output."""
    gpa_gain = acq.seq_provider.gpa_gain #V/a
    grad_eff = acq.seq_provider.grad_eff #T/m/a
    return np.divide(grad_strength,np.multiply(gpa_gain, grad_eff))

def run_fid(f0, shims):
    """Call the FID sequence with the specified shims."""
    #store and update the acquisition parameters
    initial_f0      = glob.parameter.larmor_frequency
    initial_shim    = glob.parameter.gradient_offset
    glob.update_parameters(larmor_frequency=f0)
    glob.update_parameters(gradient_offset = Dimensions(x=shims[0], y=shims[1], z=shims[2]))
    acq.set_sequence(sequence=seq)
    acq_data: AcquisitionData = acq.run()
    #restore the acquistion parameters
    glob.update_parameters(larmor_frequency=initial_f0)
    glob.update_parameters(gradient_offset =initial_shim)
    return acq_data

start_range     = 0.1  #initial step size in mT/m
end_range       = 0.01 #final step size in mT/m
num_dummies     = 3     #Dummies to avoid saturation effects biasing the first FID measurements

shims_current   = glob.parameter.gradient_offset
shims_current   = np.array([shims_current.x, shims_current.y,shims_current.z])    #convert Dimensions to list 
shims_current   *= np.multiply(acq.seq_provider.gpa_gain,acq.seq_provider.grad_eff)  #convert gradient offsets from mV to mT/m
f_0             = glob.parameter.larmor_frequency
# %%
# Run shimming process
shim_range = start_range
shims_best = shims_current

shims_current_mv    = grad_mt_to_mv(shims_current)

for idx in range(num_dummies): #run dummy scans
    dummy_data = run_fid(f_0, shims_current_mv)

data        = run_fid(f_0, shims_current_mv)                        #acquire data with current shims
acq_data    = np.mean(data.raw, axis=0)[0].squeeze()
data_fft    = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
amp_best    = np.max(np.abs(data_fft))

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
    shims_current_mv    = grad_mt_to_mv((shims_best[0]+shim_range/2, shims_best[1],shims_best[2]))
    acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
    data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
    amp_1               = np.max(np.abs(data_fft))

    shims_current_mv    = grad_mt_to_mv((shims_best[0]-shim_range/2, shims_best[1],shims_best[2]))
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
    shims_current_mv    = grad_mt_to_mv((shims_best[0], shims_best[1]+shim_range/2,shims_best[2]))
    acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
    data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
    amp_1               = np.max(np.abs(data_fft))

    shims_current_mv    = grad_mt_to_mv((shims_best[0], shims_best[1]-shim_range/2,shims_best[2]))
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
    shims_current_mv    = grad_mt_to_mv((shims_best[0], shims_best[1],shims_best[2]+shim_range/2))
    acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
    data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
    amp_1               = np.max(np.abs(data_fft))

    shims_current_mv    = grad_mt_to_mv((shims_best[0], shims_best[1],shims_best[2]-shim_range/2))
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
shims_current_mv    = grad_mt_to_mv((shims_best[0], shims_best[1],shims_best[2]))
acq_data            = np.mean(run_fid(f_0, shims_current_mv).raw, axis=0)[0].squeeze()
data_fft            = np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))
amp_2               = np.max(np.abs(data_fft))

#Plot the FID and spectrum after shimming
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

#Write current f0 and gradient offsets to globals
glob.update_parameters(larmor_frequency=f_0-f_0_offset, gradient_offset=Dimensions(x=shims_current_mv[0], y=shims_current_mv[1], z=shims_current_mv[2]))

snr = signal_to_noise_ratio(data_fft, dwell_time=dwell_time)

# Add information to acquisition data
# acq_data.add_info({
#     "adc-indo": "Shimming",
#     "true f0": f_0 - f_0_offset,
#     "magnitude spectrum max": amp_best,
#     "snr dB": snr,
# })

print("Shim offsets: ", shims_best, "mT/m")
print("Shim offsets: ", grad_mt_to_mv(shims_best), " mV")
print(f"Frequency offset [Hz]: {f_0_offset}\nNew frequency f0 [Hz]: {f_0 - f_0_offset}")
print(f"Frequency spectrum max.: {amp_best}")
print("SNR [dB]: ", snr)

# %%
# Save acquisition data

# acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\Jana")
# acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\brain-slice")
#acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\in-vivo")
# %%
