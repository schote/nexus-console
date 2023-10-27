"""Execution of a spin echo experiment using the acquisition control."""
# %%
# imports
import numpy as np
import matplotlib.pyplot as plt
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.spcm_control.acquisition_control import AcquistionControl
from console.utilities.spcm_data_plot import plot_spcm_data
from console.spcm_control.ddc import apply_ddc
from matplotlib.colors import LogNorm
from scipy.signal import butter, filtfilt

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration)

# %%
# Sequence filename
filename = "se_cartesian_64-pe"

seq_path = f"../sequences/export/{filename}.seq"

f_0 = 2037529.6875

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=6.0,
    fov_scaling=Dimensions(
        # x=0.5,
        x=9.,
        y=400.,
        # x=0.,
        # y=0.,
        z=0.,
    ),
    fov_offset=Dimensions(x=0., y=0., z=0.),
    downsampling_rate=200,
    adc_samples=500,
)

# Perform acquisition
acq.run(parameter=params, sequence=seq_path, num_averages=7)


# %%
# First argument data from channel 0 and 1,
# second argument contains the phase corrected echo
ksp = np.mean(acq.raw_data, axis=0)
plt.imshow(np.abs(ksp), cmap="gray", norm=LogNorm(vmin=0.1, vmax=100), aspect=ksp.shape[1]/ksp.shape[0])
plt.show()

# %%
# Reconstruction
img = np.fft.fftshift(np.fft.fft2(ksp))
plt.imshow(np.abs(img), cmap="gray", aspect=ksp.shape[1]/ksp.shape[0])
plt.show()
# %%

np.save("/home/schote01/data/kspace_20-10-23/20avg_6fovx_400fovy_0fovz.npy", acq.raw_data)
# %%
