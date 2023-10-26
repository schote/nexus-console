"""Transmit power calibration (flip angle)."""
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
from console.utilities.reconstruction.calibrate import tx_adjust

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration_file=configuration, console_log_level=logging.WARNING, file_log_level=logging.DEBUG)

# %%
# Construct and plot sequence
seq, flip_angles = sequences.calibration.se_tx_adjust.constructor(n_steps=20, repetition_time=500e-3, echo_time=0.012)

# Optional:
# acq.seq_provider.from_pypulseq(seq)
# seq_unrolled = acq.seq_provider.unroll_sequence(larmor_freq=2e6, grad_offset=Dimensions(0, 0, 0))
# fig, ax = plot_unrolled_sequence(seq_unrolled)

# %%
# Larmor frequency:
f_0 = 2037729.6875

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=1.0,
    adc_samples=256,
    gradient_offset=Dimensions(0, 0, 0),
    num_averages=1,
)

# Perform acquisition
acq_data: AcquisitionData = acq.run(parameter=params, sequence=seq)

# %%
# Average and take data of first coil (channeo 0)
fa_fit, rx_peaks = tx_adjust(acq_data.raw, flip_angles=flip_angles)

fig, ax = plt.subplots(1, 1, figsize=(10, 5))
ax.plot(np.degrees(fa_fit[0, ...]), fa_fit[1, ...])
ax.scatter(np.degrees(flip_angles), rx_peaks, marker="x", color="tab:orange")
ax.set_ylabel("Abs. FFT spectrum peak [a.u.]")
_ = ax.set_xlabel("Flip angle [°]")

# %%
