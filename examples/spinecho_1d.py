"""Experiment to acquire a spin echo spectrum."""

import matplotlib.pyplot as plt
import numpy as np

import console.spcm_control.globals as glob
import console.utilities.sequences as sequences
from console.interfaces.interface_acquisition_data import AcquisitionData
from console.spcm_control.acquisition_control import AcquisitionControl

# Create acquisition control instance
acq = AcquisitionControl(configuration_file="example_device_config.yaml")

# Construct a spin echo based spectrum sequence
seq = sequences.se_spectrum.constructor(
    echo_time=12e-3, rf_duration=200e-6, use_sinc=False
)

# Update global acquisition parameters
glob.update_parameters(larmor_frequency=2.0395e6)

# Run the acquisition
acq.set_sequence(sequence=seq)
acq_data: AcquisitionData = acq.run()

# Get decimated data from acquisition data object
data = acq_data.raw.squeeze()

# Calculate FFT
data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(data)))
fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, acq_data.dwell_time))

# Plot spectrum
fig, ax = plt.subplots(1, 1, figsize=(10, 5))
ax.plot(fft_freq, np.abs(data_fft))
ax.set_ylabel("Abs. FFT Spectrum [a.u.]")
ax.set_xlabel("Frequency [Hz]")

# Add information to the acquisition data
acq_data.add_info({
    "note": "Example spin echo spectrum experiment"
})

# Write acquisition data object
acq_data.save()

# Delete the acquisition control, which disconnects from the measurement cards
del acq
