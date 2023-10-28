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

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Construct sequence
seq = sequences.tse.tse_v1.constructor(
    echo_time=15e-3,
    repetition_time=600e-3,
    etl=7,
    rf_duration=400e-6,
    ro_bandwidth=20e3,
    fov=Dimensions(x=220e-3, y=220e-3, z=225e-3),
    n_enc=Dimensions(x=64, y=64, z=25)
)

# %%
# Larmor frequency:
f_0 = 2035529.0

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=6,
    adc_samples=500,
    fov_scaling=Dimensions(
        x=2.,
        y=2.,
        z=2.,
    ),
    gradient_offset=Dimensions(0, 0, 0),
    num_averages=10,
)

# Perform acquisition
acq_data: AcquisitionData = acq.run(parameter=params, sequence=seq)

# %%
# First argument data from channel 0 and 1,
# second argument contains the phase corrected echo
data = np.mean(acq_data.raw, axis=0)[0].squeeze()

acq_data.write(save_unprocessed=True)


# %%
del acq

# %%
