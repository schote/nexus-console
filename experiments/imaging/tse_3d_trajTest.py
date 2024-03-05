"""3D turbo spin echo sequence."""
# %%
# imports
import logging

import matplotlib.pyplot as plt
import numpy as np

import console.utilities.sequences as sequences
from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions

# %%
# Create acquisition control instance
configuration = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Create sequence
dim = Dimensions(x=5, y=120, z=100)

ro_bw = 20e3
te = 16e-3
# te = 25e-3

seq, traj, kdims = sequences.tse.tse_3d_trajTest.constructor(
    echo_time=te,
    repetition_time=600e-3,
    etl=7,
    gradient_correction=160e-6,
    rf_duration=200e-6,
    fov=Dimensions(x=200e-3, y=240e-3, z=200e-3),
    channel_ro="y",
    channel_pe1="z",
    channel_pe2="x",
    ro_bandwidth=ro_bw,
    n_enc=dim
)
# Optional: overwrite sequence name (used to identify experiment data)
seq.set_definition("Name", "tse_3d")
# If z=1, image acquisition is 2D
# seq.set_definition("Name", "tse_2d")

# Calculate decimation:
# adc_duration = dim.x / ro_bw; num_samples = adc_duration * spcm_sample_rate; decimation = num_samples / dim.x
# => decimation = spcm_sample_rate / ro_bw
decimation = int(acq.rx_card.sample_rate * 1e6 / ro_bw)

# %%
#Unroll and run sequence

# Larmor frequency:
f_0 = 1964408.0

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=3.4,
    fov_scaling=Dimensions(
        # Compensation of high impedance
        x=1/0.85,
        y=1/0.85,
        z=1/0.85,
    ),
    decimation=decimation,
    gradient_offset=Dimensions(x=19.22, y=25.36, z=1.08)

    # num_averages=10,
    # averaging_delay=1,
)

# Perform acquisition
acq.set_sequence(parameter=params, sequence=seq)
acq_data: AcquisitionData = acq.run()

# %%
#sort data in to kspace array
ksp = sequences.tse.tse_3d_trajTest.sort_kspace(acq_data.raw, traj, kdims).squeeze()


# %%
img = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp)))


idx = int(img.shape[0]/2)
fig, ax = plt.subplots(1, 2, figsize=(8, 4))
if len(img.shape) == 3:
    ax[0].imshow(np.abs(ksp[idx, ...]), cmap="gray")
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
fig.set_tight_layout(tight=0.)
fig.set_facecolor("black")



# %%

acq_data.add_info({
    "subject": "brain_slice, tse_tom - FOV:240,200,200, ETL = 7, herman_preamp_plus_miteq_noise",
    "echo_time": te,
    "dim": [dim.x, dim.y, dim.z],
    # "subject": "brain-slice",
    # "sequence_info": "etl = 7, optimized grad correction",
})

acq_data.add_data({
    "trajectory": traj,
    "kspace": ksp,
    "image": img
})



acq_data.save(save_unprocessed=False, user_path=r"C:\Users\Tom\Desktop\spcm-data\20240305 - TSE test")
#acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\in-vivo")
# acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\b0-map")
# acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\brain-slice")
# %%
del acq
