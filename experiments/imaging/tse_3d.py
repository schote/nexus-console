"""3D turbo spin echo sequence."""
# %%
# imports
import logging

import matplotlib.pyplot as plt
import numpy as np

import console.spcm_control.globals as glob
import console.utilities.sequences as sequences
from console.interfaces.interface_acquisition_data import AcquisitionData
from console.interfaces.interface_acquisition_parameter import Dimensions
from console.spcm_control.acquisition_control import AcquisitionControl

# %%
# Create acquisition control instance
configuration = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Create sequence
num_voxels  = Dimensions(x=1, y=120, z=100)
ro_bw       = 20e3
te          = 50e-3

seq, traj, kdims = sequences.tse.tse_3d.constructor(
    echo_time           = te,
    repetition_time     = 2000e-3,
    etl                 = 22,
    dummies             = 3,
    trajectory          = 'linear',
    gradient_correction = 160e-6,
    rf_duration         = 200e-6,
    fov                 = Dimensions(x=200e-3, y=240e-3, z=200e-3),
    channel_ro          = "y",
    channel_pe1         = "z",
    channel_pe2         = "x",
    ro_bandwidth        = ro_bw,
    n_enc               = num_voxels
)
# Optional: overwrite sequence name (used to identify experiment data)
seq.set_definition("Name", "tse_3d")

# Calculate decimation:
decimation = int(acq.rx_card.sample_rate * 1e6 / ro_bw)
glob.update_parameters(decimation = decimation)

# %%
#Unroll and run sequence

# Perform acquisition
acq.set_sequence(sequence=seq)
acq_data: AcquisitionData = acq.run()

# %%
#sort data in to kspace array
ksp = sequences.tse.tse_3d.sort_kspace(acq_data.raw, traj, kdims).squeeze()

# %%
#plot data
if len(np.shape(ksp)) == 4:
    img = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp[0,...])))
else:
    img = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp)))

idx = int(img.shape[0]/2)
fig, ax = plt.subplots(1, 2, figsize=(8, 4))
if len(ksp.shape) == 3:
    ax[0].imshow(np.abs(ksp[idx, ...]), cmap="gray")
    ax[1].imshow(np.abs(img[idx, ...]), cmap="gray")
elif len(ksp.shape) == 4:
    ax[0].imshow(np.abs(ksp[0,idx, ...]), cmap="gray")
    ax[1].imshow(np.abs(img[idx, ...]), cmap="gray")
else:
    ax[0].imshow(np.abs(ksp), cmap="gray")
    ax[1].imshow(np.abs(img), cmap="gray")
plt.show()


# %%
# 3D plot
num_slices = img.shape[0]
num_cols = int(np.ceil(np.sqrt(num_slices)))
num_rows = int(np.ceil(num_slices/num_cols))
fig, ax = plt.subplots(num_rows, num_cols, figsize=(10, 10))
ax = ax.ravel()
total_max = np.amax(np.abs(img))
total_min = 0   # np.amin(np.abs(img))
for k, x in enumerate(img[:, ...]):
    ax[k].imshow(np.abs(x), vmin=total_min, vmax=total_max, cmap="gray")
    ax[k].axis("off")
_ = [a.remove() for a in ax[k+1:]]
fig.set_tight_layout(True)
fig.set_facecolor("black")


# %%

acq_data.add_info({
    "subject": "Brain phantom",
    "echo_time": te,
    "dim": [num_voxels.x, num_voxels.y, num_voxels.z],
    # "sequence_info": "etl = 7, optimized grad correction",
})

acq_data.add_data({
    "trajectory": np.array(traj),
    "kspace": ksp,
    "image": img
})

acq_data.save(save_unprocessed=False, user_path=r"C:\Users\Tom\Desktop\spcm-data\20240325 - Phantom")

# %%
del acq
