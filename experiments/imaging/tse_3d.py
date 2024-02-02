"""3D turbo spin echo sequence."""
# %%
# imports
import logging
import numpy as np
import matplotlib.pyplot as plt
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
import console.utilities.sequences as sequences

# %%
# Create acquisition control instance
configuration = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Construct sequence
seq, traj = sequences.tse.tse_3d.constructor(
    echo_time=20e-3,
    repetition_time=600e-3,
    etl=7,
    gradient_correction=0,
    adc_correction=0,
    rf_duration=200e-6,
    ro_bandwidth=20e3,
    fov=Dimensions(x=120e-3, y=120e-3, z=120e-3),
    n_enc=Dimensions(x=64, y=64, z=1)
    # n_enc=Dimensions(x=64, y=64, z=32)
)
# Optional: overwrite sequence name (used to identify experiment data)
seq.set_definition("Name", "tse_3d")

# %%
# Larmor frequency:
f_0 = 1964390.0 # leiden

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=2.9623,  # leiden
    fov_scaling=Dimensions(
        # Ball phantom
        # x=1.,
        # y=0.7,

        # Brain slice 64 x 64
        # x=0.5,
        # y=0.3,

        # Brain slice 128 x 128
        # x=0.5,
        # x=0.825,
        # y=0.275,

        # # Scope
        # x=1.,
        # y=1.,
        # z=1.,
    ),
    gradient_offset=Dimensions(0, 0, 0),

    # num_averages=10,
    # averaging_delay=1,
)

# Perform acquisition
acq.set_sequence(parameter=params, sequence=seq)
acq_data: AcquisitionData = acq.run()

# %%

ksp = np.mean(acq_data.raw, axis=0)[0].squeeze()

# TODO: Reordering of k-space (inside-out trajectory)

img = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp), axes=[-2, -1]))

fig, ax = plt.subplots(1, 2, figsize=(10, 5), dpi=300)
ax[0].imshow(np.abs(ksp), cmap="gray")
ax[1].imshow(np.abs(img), cmap="gray")
plt.show()


# %%

acq_data.add_info({
    "subject": ""
})

acq_data.save(save_unprocessed=False, user_path="~/spcm-console-data/")


# %%
del acq
