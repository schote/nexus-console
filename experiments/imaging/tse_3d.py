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
# Construct sequence
dim = Dimensions(x=64, y=64, z=1)
# dim = Dimensions(x=16, y=16, z=1)
# dim = Dimensions(x=64, y=64, z=32)

seq, traj = sequences.tse.tse_3d.constructor(
    # echo_time=6e-3,
    echo_time=20e-3,
    repetition_time=600e-3,
    # etl=7,
    etl=1,
    gradient_correction=0,
    adc_correction=0,
    rf_duration=200e-6,
    ro_bandwidth=20e3,
    fov=Dimensions(x=150e-3, y=150e-3, z=150e-3),
    n_enc=dim
)
# Optional: overwrite sequence name (used to identify experiment data)
# seq.set_definition("Name", "tse_3d")
# If z=1, image acquisition is 2D
seq.set_definition("Name", "tse_2d")

# %%
# Larmor frequency:
f_0 = 1964500.0


# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    # b1_scaling=2.9623,  # leiden
    b1_scaling=3.53,
    fov_scaling=Dimensions(
        # Ball phantom
        # x=1.,
        # y=0.7,
        # z=0.,

        # Brain slice 64 x 64
        # x=0.5,
        # y=0.3,

        # Brain slice 128 x 128
        # x=0.5,
        # x=0.825,
        # y=0.275,

        # Scope
        x=1.,
        y=1.,
        z=1.,
    ),
    gradient_offset=Dimensions(0, 0, 0),
    decimation=400,

    # num_averages=10,
    # averaging_delay=1,
)

# Perform acquisition
acq.set_sequence(parameter=params, sequence=seq)
acq_data: AcquisitionData = acq.run()

ksp = sequences.tse_3d.sort_kspace(acq_data.raw, trajectory=traj, dim=dim)
ksp = ksp.squeeze()


# %%
img = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp), axes=[-2, -1]))

fig, ax = plt.subplots(1, 2, figsize=(10, 5), dpi=300)
ax[0].imshow(np.abs(ksp), cmap="gray", aspect=ksp.shape[-1]/ksp.shape[-2])
ax[1].imshow(np.abs(img), cmap="gray", aspect=img.shape[-1]/img.shape[-2])
plt.show()


# %%

acq_data.add_info({
    "subject": "sphere, 8cm"
})

acq_data.save(save_unprocessed=True, user_path=r"C:\Users\Tom\Desktop\spcm-data")


# %%
del acq
