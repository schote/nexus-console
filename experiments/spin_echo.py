"""Execution of a spin echo experiment using the acquisition control."""
# %%
# imports
import numpy as np
import matplotlib.pyplot as plt
from console.spcm_control.acquisition_control import AcquistionControl, AcquisitionParameter, Dimensions

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
filename = "se_spectrum_200us-rect"

seq_path = f"../sequences/export/{filename}.seq"

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=2.031e6,
    # b1_scaling=0.0035,
    b1_scaling=0.007,
    fov_scaling=Dimensions(
        x=0.,   #0.0001,
        y=0.0001,
        z=0.0001,
    ),
    fov_offset=Dimensions(
        x=0,
        y=0,
        z=0,
    ),
    downsampling_rate=200
)

# Perform acquisition
acq.run(parameter=params, sequence=seq_path)

data_fft = np.fft.fftshift(np.fft.fft(acq.data[0]))
fft_freq = np.fft.fftshift(np.fft.fftfreq(acq.data[0].size, acq.dwell_time))

fig, ax = plt.subplots(1, 2, figsize=(10, 4))
ax[0].plot(acq.rx_card.rx_data[0])
ax[1].plot(fft_freq, np.abs(data_fft))
ax[1].set_xlim([-10e3, 10e3])

# %%
# Delete acquisition control instance to disconnect from cards
del acq
# %%
