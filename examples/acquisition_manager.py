"""Nexus acquisition manager example."""
# %%
import matplotlib.pyplot as plt
import numpy as np

import console
from console.interfaces.dimensions import Dimensions
from console.service.acquisition_manager import AcquisitionControlManager
from console.utilities.sequences import tse_3d

# %%

seq, _ = tse_3d.constructor(
    echo_time=20e-3,
    repetition_time=600e-3,
    etl=5,
    rf_duration=200e-6,
    fov=Dimensions(x=0.2, y=0.2, z=0.2),
    channel_ro="y",
    channel_pe1="z",
    channel_pe2="x",
    ro_bandwidth=20e3,
    n_enc=Dimensions(x=1, y=100, z=20),
)

# %%
with AcquisitionControlManager() as mngr:

    console.parameter.larmor_frequency = 1.995e6
    console.parameter.gradient_offset = Dimensions(x=1, y=10, z=100)
    print(console.parameter)

    # # acq_control.set_sequence("/home/schote01/code/spectrum-console-experiments/service/2d_tse.seq")
    mngr.acquisition.set_sequence(sequence=seq, parameter=console.parameter)
    data = mngr.acquisition.run()

# %%

fig, ax = plt.subplots(1, 1, figsize=(5, 5))
_ = ax.plot(np.abs(data.raw.squeeze().T))


# %%
