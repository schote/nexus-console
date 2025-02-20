"""Nexus acquisition manager example."""
# %%
from console.service.acquisition_manager import AcquisitionControlManager
from console.interfaces.dimensions import Dimensions
from console.utilities.sequences import tse_3d
import matplotlib.pyplot as plt
import numpy as np

from console.interfaces.dimensions import Dimensions
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
with AcquisitionControlManager() as (acq, params):
    
    params.set_larmor_frequency(1.995e6)
    params.set_gradient_offset(Dimensions(x=1, y=10, z=100))
    
    # # acq_control.set_sequence("/home/schote01/code/spectrum-console-experiments/service/2d_tse.seq")
    acq.set_sequence(sequence=seq)
    data = acq.run()
    
    print("larmor frequency: ", params.get_larmor_frequency())
    print("gradient offsets: ", params.get_gradient_offset())
    
    params.set_larmor_frequency(2.0322e6)
    params.set_gradient_offset(Dimensions(x=0, y=0, z=0))
    
    print("larmor frequency: ", params.get_larmor_frequency())
    print("gradient offsets: ", params.get_gradient_offset())
    

# %%

fig, ax = plt.subplots(1, 1, figsize=(5, 5))
_ = ax.plot(np.abs(data.raw.squeeze().T))


# %%
