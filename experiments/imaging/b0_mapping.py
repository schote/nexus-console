"""3D turbo spin echo sequence."""
# %%
# imports
import logging

import matplotlib.pyplot as plt
import numpy as np
from skimage.restoration import unwrap_phase

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
dim     = Dimensions(x=5, y=120, z=100)

ro_bw   = 20e3
te      = 18e-3
tr      = 600e-3
etl     = 5
echo_shift = 300e-6
echo_shift = 200e-6

# Optional: overwrite sequence name (used to identify experiment data)

decimation = int(acq.rx_card.sample_rate * 1e6 / ro_bw)
glob.update_parameters(decimation = decimation)


# %%
#Aquire unshifted data
seq, traj, kdims = sequences.tse.b0_mapping.constructor(
    echo_time=te,
    repetition_time=tr,
    etl=etl,
    echo_shift = echo_shift,
    dummies = 10,
    gradient_correction=160e-6,
    rf_duration=200e-6,
    fov=Dimensions(x=200e-3, y=240e-3, z=200e-3),
    channel_ro="y",
    channel_pe1="z",
    channel_pe2="x",
    ro_bandwidth=ro_bw,
    n_enc=dim
)
seq.set_definition("Name", "b0_mapping")

# Perform acquisition
acq.set_sequence(sequence=seq)
acq_data: AcquisitionData = acq.run()


# %%
#sort data in to kspace array
ksp_unshifted, ksp_shifted  = sequences.tse.b0_mapping.sort_kspace(acq_data.raw, traj, kdims)


# %%
img_unshifted   = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp_unshifted.squeeze())))
img_shifted     = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp_shifted.squeeze())))

img_mask        = np.abs(img_unshifted)>(0.1*np.max(np.abs(img_shifted)))

phase_corr      = np.mean(np.angle(img_unshifted*img_mask))*0
phase_diff      = np.angle(img_shifted*np.exp(-1j*phase_corr)) - np.angle(img_unshifted*np.exp(-1j*phase_corr))
phase_diff      = unwrap_phase(phase_diff)
b0_map          = phase_diff/(2*np.pi*echo_shift)

idx = int(img_unshifted.shape[0]/2)
fig, ax = plt.subplots(2, 3, figsize=(8, 4))
ax[0][0].imshow(np.abs(img_unshifted[idx, ...]), cmap="gray")
ax[0][1].imshow(np.abs(img_shifted[idx, ...]), cmap="gray")
ax[0][2].imshow((b0_map*img_mask)[idx,...],vmin = -1000, vmax = 500 )
ax[1][0].imshow(np.angle(img_unshifted[idx, ...]*np.exp(-1j*phase_corr)), cmap="gray", vmin = -np.pi, vmax = np.pi)
ax[1][1].imshow(np.angle(img_shifted[idx, ...]*np.exp(-1j*phase_corr)), cmap="gray", vmin = -np.pi, vmax = np.pi)
ax[1][2].imshow((phase_diff*img_mask)[idx,...],vmin = -np.pi, vmax = np.pi )
plt.show()



# %%
# 3D plot
num_slices = img_unshifted.shape[0]
num_cols = int(np.ceil(np.sqrt(num_slices)))
num_rows = int(np.ceil(num_slices/num_cols))
fig, ax = plt.subplots(num_rows, num_cols, figsize=(10, 10))
ax = ax.ravel()
total_max = np.amax(np.abs(img_unshifted))
total_min = 0   # np.amin(np.abs(img))
for k, x in enumerate(img_unshifted[:, ...]):
    ax[k].imshow(np.abs(x), vmin=total_min, vmax=total_max, cmap="gray")
    ax[k].axis("off")
_ = [a.remove() for a in ax[k+1:]]
fig.set_tight_layout(tight=0.)
fig.set_facecolor("black")



# %%

acq_data.add_info({
    "subject": "brain_slice, B0_map",
    "echo_time": te,
    "echo_shift": echo_shift,
    "dim": [dim.x, dim.y, dim.z],
    # "subject": "brain-slice",
    # "sequence_info": "etl = 7, optimized grad correction",
})

acq_data.add_data({
    "trajectory": np.array(traj),
    "kspace_unshifted": ksp_unshifted,
    "kspace_shifted": ksp_shifted,
    "image": img_unshifted
})

acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data\20240319 - B0 mapping")


# %%
del acq
