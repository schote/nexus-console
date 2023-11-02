"""Spin-echo projection."""
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
acq = AcquistionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%

bw = 20e3
samples = 100

# Construct and plot sequence
seq = sequences.se_projection.constructor(
    fov=0.24, 
    readout_bandwidth=bw,
    gradient_correction=300e-6,  #690e-6,
    num_samples=samples,
    echo_time=20e-3,
    rf_duration=200e-6, 
    use_sinc=False,
    channel="y"
)

# Optional:
acq.seq_provider.from_pypulseq(seq)
seq_unrolled = acq.seq_provider.unroll_sequence(larmor_freq=2e6, fov_scaling=Dimensions(1., 1., 1.), grad_offset=Dimensions(0, 0, 0))
fig, ax = plot_unrolled_sequence(seq_unrolled)

# %%
# Larmor frequency:
# f_0 = 2035529.0
f_0 = 1964390.0

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=2.693,
    # adc_samples=2000,
    adc_samples=500,
    fov_scaling=Dimensions(
        x=1.,
        y=1.,
        z=1.,
    ),
    gradient_offset=Dimensions(0, 0, 0),
    num_averages=5,
    averaging_delay=5,
)

# Perform acquisition
acq_data: AcquisitionData = acq.run(parameter=params, sequence=seq)

# %%
# FFT

# data = np.mean(acq_data.raw, axis=0) if acq_data.raw.shape[0] > 1 else acq_data.raw
data = np.squeeze(acq_data.raw)
data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(data), axis=-1))
fft_freq = np.fft.fftshift(np.fft.fftfreq(data_fft.shape[-1], acq_data.dwell_time))

# max_spec = np.max(np.abs(data_fft))
# f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]
# print("True f0 [Hz]: ", f_0 - f_0_offset)

# print("Acquisition data shape: ", acq_data.raw.shape)

# # Plot spectrum
# fig, ax = plt.subplots(1, 1, figsize=(10, 6))
# ax.plot(fft_freq, np.abs(data_fft)) 
# ax.set_xlim([-20e3, 20e3])
# ax.set_ylim([0, max_spec*1.05])
# ax.set_ylabel("Abs. FFT Spectrum [a.u.]")
# _ = ax.set_xlabel("Frequency [Hz]")


# %%
# Plot phase information
fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for k in range(data_fft.shape[0]):
    ax.plot(fft_freq, np.degrees(np.angle(data_fft[k, ...])))

# plt.plot(fft_freq, np.degrees(np.angle(data_fft)))

ax.set_xlim([-1e3, 1e3])


# %%
# Plot time domain signal
time_axis = np.arange(acq_data.raw.shape[-1]) * acq_data.dwell_time
raw_data = np.squeeze(acq_data.raw)

for k in range(raw_data.shape[0]):

    raw = raw_data[k, ...]

    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    ax.plot(time_axis*1e3, np.abs(raw))
    ax.plot(time_axis*1e3, np.real(raw))
    ax.plot(time_axis*1e3, np.imag(raw))
    ax.set_ylabel("Amplitude")
    ax.set_xlabel("Time [ms]")

    signal_center = time_axis[np.argmax(np.abs(raw))]
    adc_duration = acq_data.dwell_time * raw.shape[-1]
    expected_center = adc_duration / 2

    print("Signal center [ms]: ", signal_center*1e3)
    print("Expected center [ms]: ", expected_center*1e3)
    print("Shift [us]:", (signal_center - expected_center)*1e6)

# %%
acq_data.write()

# %%
del acq

# %%
