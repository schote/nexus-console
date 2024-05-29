"""Experiment to acquire a spin echo spectrum."""
import torch
import logging

import matplotlib.pyplot as plt
import numpy as np

import console.utilities.sequences as sequences
from console.spcm_control.acquisition_control import AcquisitionControl
from console.interfaces.interface_acquisition_data import AcquisitionData
from console.interfaces.interface_acquisition_parameter import AcquisitionParameter

# Create acquisition control instance
acq = AcquisitionControl(
    configuration_file="device_config.yaml",
    console_log_level=logging.DEBUG,
    file_log_level=logging.DEBUG,
    rf_amps=[1.0,0.75,0.5,0.25,0.5,0.75,0.5,0.25],
    rf_phases=[0.,45.,90.,135.,0.,45.,90.,135.]
    
)

# Construct a spin echo based spectrum sequence
seq = sequences.se_spectrum.constructor(
    echo_time=1e-6,          # 12 ms echo time
    rf_duration=1e-6,      # 200 us RF pulseq duration
    adc_duration= 1e-6,
    time_bw_product=1,
    use_sinc=False           # Do not use sinc pulse, but block pulse
)

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=123e6,     # Set Larmor freqency in MHz
    decimation=200,             # Set decimation factor for down-sampling
)

# Run the acquisition
acq.set_sequence(sequence=seq) #make it between 0 to 1
acq_data: AcquisitionData = acq.run()



# Get decimated data from acquisition data object
'''
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
'''
# Delete the acquisition control, which disconnects from the measurement cards
del acq
