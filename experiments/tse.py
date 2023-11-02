"""Turbo spin echo sequence."""
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
from scipy.signal import decimate

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Construct sequence
seq, traj = sequences.tse.tse_v1_2d.constructor(
    echo_time=20e-3,
    repetition_time=300e-3,
    etl=1,
    gradient_correction=510e-6,
    rf_duration=200e-6,
    ro_bandwidth=20e3,
    fov=Dimensions(x=220e-3, y=220e-3, z=225e-3),
    n_enc=Dimensions(x=64, y=64, z=0)
    # n_enc=Dimensions(x=128, y=128, z=0)
)

# %%
# Larmor frequency:
f_0 = 1964390.0

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    # b1_scaling=2.693,
    b1_scaling=2.9623,
    adc_samples=512,
    downsampling_rate=200,
    fov_scaling=Dimensions(
        # Ball phantom
        # x=1.,
        # y=0.7,
        # Brain slice 64 x 64
        x=0.5,
        y=0.3,

        # Brain slice 128 x 128
        # x=0.5,
        # x=0.825,
        # y=0.275,

        z=1.,
    ),
    gradient_offset=Dimensions(0, 0, 0),
    num_averages=1,
    # num_averages=10,
    # averaging_delay=2,
)

# Perform acquisition
acq_data: AcquisitionData = acq.run(parameter=params, sequence=seq)

# %%
# Load saved data
raw = np.load("/home/schote01/spcm-console/2023-11-01-session/2023-11-01-110449-2d_tse_v1/raw_data.npy")
ksp = np.mean(raw, axis=0)[0].squeeze()

# %%

# First argument data from channel 0 and 1,
# second argument contains the phase corrected echo
# ksp = np.mean(acq_data.raw, axis=0)[0].squeeze()

# Use scipy decimate function to reduce k-space readout from 500 to 128 
n_pe = ksp.shape[0]
ksp_dec = decimate(ksp, int(ksp.shape[1]/ksp.shape[0]), axis=1)
window_start = int(ksp_dec.shape[1]/2 - n_pe/2)
ksp_dec = ksp_dec[:, window_start:window_start+n_pe]

img = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp_dec), axes=[-2, -1]))

fig, ax = plt.subplots(1, 2, figsize=(10, 5), dpi=300)
ax[0].imshow(np.abs(ksp_dec), cmap="gray")
ax[1].imshow(np.abs(img), cmap="gray")
plt.show()




# %%

acq_data.add_info({
    "comment": "Lukas thumb",
    "processing": "512 ro samples from DDC, scipy decimation to 64"
})

acq_data.write(save_unprocessed=True)


# %%
del acq

# %%
