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
from console.utilities.reconstruction.calibrate import flip_angle_fit

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Construct and plot sequence
seq, flip_angles = sequences.calibration.fid_tx_adjust.constructor(
    n_steps=50,
    max_flip_angle=5*np.pi/4,
    repetition_time=2,
    rf_duration=200e-6,
    use_sinc=False,
)

# Optional:
# acq.seq_provider.from_pypulseq(seq)
# seq_unrolled = acq.seq_provider.unroll_sequence(larmor_freq=2e6, grad_offset=Dimensions(0, 0, 0))
# fig, ax = plot_unrolled_sequence(seq_unrolled, seq_range=(0, 5000000))

# %%
# Larmor frequency:
# f_0 = 2035529.0 # berlin
f_0 = 1964690.0 # leiden

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=2.9623,
    adc_samples=256,
    gradient_offset=Dimensions(0, 0, 0),
    num_averages=1,
)

# Perform acquisition
acq_data: AcquisitionData = acq.run(parameter=params, sequence=seq)

# %%
# Average and take data of first coil (channeo 0)

# fa_fit, rx_peaks = flip_angle_fit(acq_data.raw, flip_angles=flip_angles)
# fig, ax = plt.subplots(1, 1, figsize=(10, 5))
# ax.plot(np.degrees(fa_fit[0, ...]), fa_fit[1, ...])
# ax.scatter(np.degrees(flip_angles), rx_peaks, marker="x", color="tab:orange")
# ax.set_ylabel("Abs. FFT spectrum peak [a.u.]")
# _ = ax.set_xlabel("Flip angle [°]")

# FFT
data = np.mean(acq_data.raw, axis=0)[0, ...]
data = np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(data), axis=-1)))

center_window = 100
window_start = int(params.adc_samples/2-center_window/2)
peak_windows = data[:, window_start:window_start+center_window]
peaks = np.max(peak_windows, axis=-1)

fig, ax = plt.subplots(1, 1, figsize=(10, 6))
ax.scatter(np.degrees(flip_angles), peaks)
ax.set_ylabel("Amplitude [a.u.]")
ax.set_xlabel("Flip angle [°]")


flip_angle_max_amp = np.degrees(flip_angles[np.argmax(peaks)])
print("True max. at flip angle: ", flip_angle_max_amp)
factor = flip_angle_max_amp / 90
print("Scale B1 by: ", factor)

# %%
acq_data.write(save_unprocessed=True)

# %%
del acq
# %%

