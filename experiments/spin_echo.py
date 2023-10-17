"""Execution of a spin echo experiment using the acquisition control."""
# %%
# imports
import numpy as np
import matplotlib.pyplot as plt
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.spcm_control.acquisition_control import AcquistionControl
from console.utilities.spcm_data_plot import plot_spcm_data

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration)

# %%
# Sequence filename

# filename = "se_spectrum_400us_sinc_8ms-te"
# filename = "se_spectrum_400us_sinc_20ms-te"
# filename = "se_spectrum_400us_sinc_30ms-te"
# filename = "se_proj_400us-sinc_20ms-te"
# filename = "se_proj_400us_sinc_12ms-te"
# filename = "se_spectrum_200us-rect"
filename = "dual-se_spec"

seq_path = f"../sequences/export/{filename}.seq"

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=2.031e6,
    b1_scaling=.1,
    fov_scaling=Dimensions(x=1., y=1., z=1.),
    fov_offset=Dimensions(x=0., y=0., z=0.),
    downsampling_rate=200
)

# Perform acquisition
acq.run(parameter=params, sequence=seq_path)

# %%

# Gate 0, channel 1
raw = acq.rx_card.rx_data[0][1]
# Filtered: Channel 1, gate 0
filtered = acq.data[1][0][:-350]

n_raw_samples = 100
t_raw = 1e3 * np.arange(n_raw_samples) / acq.f_spcm
t_filered = 1e3 * np.arange(filtered.size) * acq.dwell_time

fig, ax = plt.subplots(1, 3, figsize=(12, 3))
ax[0].plot(t_raw, raw[:n_raw_samples]),ax[0].set_title("Raw signal")
ax[1].plot(t_filered, np.abs(filtered)), ax[1].set_title("Magnitude, filtered")
ax[2].plot(t_filered, np.angle(filtered)), ax[2].set_title("Phase, filtered")
_ = [a.set_xlabel("t [ms]") for a in ax]
ax[0].set_ylabel("Magnitude [mV]")


with open('data_1.txt', 'wb') as fh:
    np.savetxt(fh, raw)


# data_fft = np.fft.fftshift(np.fft.fft(acq.data[0]))
# fft_freq = np.fft.fftshift(np.fft.fftfreq(acq.data[0].size, acq.dwell_time))

# fig, ax = plt.subplots(1, 2, figsize=(10, 4))
# ax[0].plot(acq.rx_card.rx_data[0])
# ax[1].plot(fft_freq, np.abs(data_fft))
# ax[1].set_xlim([-10e3, 10e3])

# %%

# fig, ax = plot_spcm_data(acq.unrolled_sequence)

# %%
# Delete acquisition control instance to disconnect from cards
del acq
# %%
