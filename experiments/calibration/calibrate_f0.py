"""Spin-echo spectrum."""
# %%
import logging

import matplotlib.pyplot as plt
import numpy as np

import console.spcm_control.globals as glob
from console.interfaces.interface_acquisition_data import AcquisitionData
from console.spcm_control.acquisition_control import AcquisitionControl
from console.utilities.sequences.spectrometry import fid
from console.utilities.snr import signal_to_noise_ratio

# %%
# Create acquisition control instance
configuration = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Construct FID
seq = fid.constructor(
    rf_duration=200e-6,
    adc_duration=100e-3,
    dead_time=3e-3,
    flip_angle=np.pi/2,
    )


# %%
#acquire data
current_f0 = glob.parameter.larmor_frequency


#change larmor frequency if desired
# glob.update_parameters(larmor_frequency=1964408.0)

acq.set_sequence(sequence=seq)
acq_data: AcquisitionData = acq.run()

# FFT
data = np.mean(acq_data.raw, axis=0)[0].squeeze()
data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(data)))
fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, acq_data.dwell_time))

max_spec = np.max(np.abs(data_fft))
f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]

#update global larmor frequency to measured f0
glob.update_parameters(larmor_frequency=current_f0-f_0_offset)

snr = signal_to_noise_ratio(data_fft, dwell_time=acq_data.dwell_time)


# Add information to acquisition data
acq_data.add_info({
    "adc-indo": "FID of the spin-echo, 50 ms readout",
    "true f0": current_f0 - f_0_offset,
    "magnitude spectrum max": max_spec,
    "snr dB": snr,
})

print(f"Frequency offset [Hz]: {f_0_offset}\nNew frequency f0 [Hz]: {current_f0 - f_0_offset}")
print(f"Frequency spectrum max.: {max_spec}")
print("Acquisition data shape: ", acq_data.raw.shape)
print("SNR [dB]: ", snr)

# Plot spectrum
time_axis = np.arange(data.size)*acq_data.dwell_time*1e3
fig, ax = plt.subplots(1, 2, figsize=(10, 5))
ax[0].plot(time_axis, np.abs(data))
ax[0].set_xlabel("Time [ms]")
ax[0].set_xlim((0, np.max(time_axis)))
ax[1].plot(fft_freq, np.abs(data_fft))
# ax.set_xlim([-20e3, 20e3])
ax[1].set_ylim([0, max_spec * 1.05])
ax[1].set_ylabel("Abs. FFT Spectrum [a.u.]")
ax[1].set_xlabel("Frequency [Hz]")
fig.set_tight_layout(True)
plt.show()

# %%
# Save acquisition data

# acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\Jana")
# acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\brain-slice")
acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\20240312 - B0 mapping")
# %%
