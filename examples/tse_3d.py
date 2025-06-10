"""3D turbo spin echo sequence."""
# %%
import matplotlib.pyplot as plt
import numpy as np

import console
import logging
from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.acquisition_parameter import Dimensions
from console.spcm_control.acquisition_control import AcquisitionControl
from console.utilities.sequences import tse_3d

# Create acquisition control instance
config_file = r"examples/example_device_config.yaml"
acq = AcquisitionControl(configuration_file="example_device_config.yaml",
                         file_log_level=logging.DEBUG,
                         console_log_level=logging.DEBUG)

# Create sequence
params = {
    "echo_time": 20e-3,
    "repetition_time": 600e-3,
    "etl": 7,
    "gradient_correction": 80e-6,
    "rf_duration": 200e-6,
    "fov": Dimensions(x=180e-3, y=180e-3, z=180e-3),
    "channel_ro": "z",
    "channel_pe1": "y",
    "channel_pe2": "x",
    "ro_bandwidth": 20e3,
    "n_enc": Dimensions(x=30, y=60, z=60),
}
seq, header = tse_3d.constructor(**params)

# Calculate sequence and perform acquisition
acq.set_sequence(sequence=seq, parameter=console.parameter)

#%%
# Execute the sequence and sort kspace array
acq_data: AcquisitionData = acq.run()
ksp = tse_3d.sort_kspace(acq_data.receive_data, seq)

# Image reconstruction with FFT
img = np.zeros(np.shape(ksp), dtype = complex)

for idx_avg in range(np.size(ksp, 0)):
    for idx_coil in range(np.size(ksp, 1)):
        img[idx_avg, idx_coil, ...] = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp[idx_avg, idx_coil,...])))

img = img.squeeze()
ksp = ksp.squeeze()

# Just grab the 0th coil/avg data
if np.size(np.shape(img)) == 4:
    img = img[1,...]
    ksp = ksp[1,...]
elif np.size(np.shape(img)) == 5:
    img = img[0,0,...]
    ksp = ksp[0,0,...]


# 3D magnitude plot of image slices
num_slices = img.shape[0]
num_cols = int(np.ceil(np.sqrt(num_slices)))
num_rows = int(np.ceil(num_slices / num_cols))
fig, ax = plt.subplots(num_rows, num_cols, figsize=(10, 10))
ax = ax.ravel()
total_max = np.amax(np.abs(img))
total_min = 0   # np.amin(np.abs(img))
for k, x in enumerate(img[:, ...]):
    ax[k].imshow(np.abs(x), vmin=total_min, vmax=total_max, cmap="gray")
    ax[k].axis("off")
_ = [a.remove() for a in ax[k + 1:]]
fig.tight_layout(pad=0.01)
fig.set_facecolor("black")


# Complement acquisition data
acq_data.add_info({
    "note": "sphere phantom",
    "sequence_parameter": params,
})
acq_data.add_data({
    "kspace": ksp,
    "image": img,
})

acq_data.save()

del acq

# %%
