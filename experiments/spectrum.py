"""Execution of a spin echo experiment using the acquisition control."""
# %%
# imports
import logging
import numpy as np
import matplotlib.pyplot as plt
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.spcm_control.acquisition_control import AcquistionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.utilities.plot_unrolled_sequence import plot_unrolled_sequence
import console.utilities.sequences as sequences

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration_file=configuration, console_log_level=logging.WARNING, file_log_level=logging.DEBUG)

# %%
# Construct and plot sequence
seq = sequences.se_spectrum.constructor(te=12e-3, rf_duration=400e-6, use_sinc=True)

# Optional:
acq.seq_provider.from_pypulseq(seq)
seq_unrolled = acq.seq_provider.unroll_sequence(larmor_freq=2e6, grad_offset=Dimensions(0, 0, 0))
fig, ax = plot_unrolled_sequence(seq_unrolled)

# %%
# Larmor frequency:
f_0 = 2037729.6875

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=2.5,
    adc_samples=500,
    gradient_offset=Dimensions(0, 0, 0),
    num_averages=1,
)

# Perform acquisition
acq_data: AcquisitionData = acq.run(parameter=params, sequence=seq)

# %%
# First argument data from channel 0 and 1,
# second argument contains the phase corrected echo
data = np.mean(acq_data.raw, axis=0)[0].squeeze()

# FFT
data_fft = np.fft.fftshift(np.fft.fft(data))
fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, acq_data.dwell_time))

# Print peak height and center frequency
max_spec = np.max(np.abs(data_fft))
f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]

# Add information to acquisition data
acq_data.add_info({
    "true f0": f_0 - f_0_offset,
    "magnitude spectrum max": max_spec
})

print(f"Frequency offset [Hz]: {f_0_offset}, new frequency f0 [Hz]: {f_0 - f_0_offset}")
print(f"Frequency spectrum max.: {max_spec}")
print("Acquisition data shape: ", acq_data.raw.shape)

# Plot spectrum
fig, ax = plt.subplots(1, 1, figsize=(10, 5))
ax.plot(fft_freq, np.abs(data_fft))    
ax.set_xlim([-20e3, 20e3])
ax.set_ylim([0, max_spec*1.05])
ax.set_ylabel("Abs. FFT Spectrum [a.u.]")
_ = ax.set_xlabel("Frequency [Hz]")
