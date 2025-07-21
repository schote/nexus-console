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
    console.parameter.gradient_offset = Dimensions(x=0, y=0, z=0)
    print(console.parameter)

    mngr.acquisition.set_sequence(sequence=seq, parameter=console.parameter)
    data = mngr.acquisition.run()

# %%

scan_data = np.array([rx_data.processed_data for rx_data in data.receive_data])
num_coils = np.size(scan_data, 1)

fig, ax = plt.subplots(1, num_coils, figsize=(5 * num_coils, 5))
for coil in range(num_coils):
    ax[coil].plot(np.abs(scan_data[:, coil, :]).T)
    ax[coil].set_xlabel("Sample")
    ax[coil].set_ylabel("Signal [mV]")
    ax[coil].set_title(f"Rx channel: {coil}")
fig.set_layout_engine('tight')


# %%
