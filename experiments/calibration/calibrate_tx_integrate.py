"""Transmit power calibration (flip angle)."""
# %%
import logging
from math import pi

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.utilities.sequences.calibration import se_tx_adjust, fid_tx_adjust

# %%
configuration = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Spinecho
# seq, flip_angles = se_tx_adjust.constructor(
#     echo_time=15e-3,
#     rf_duration=200e-6,
#     repetition_time=2,
#     n_steps=50,
#     flip_angle_range=(np.deg2rad(10), np.deg2rad(270)),
#     use_sinc=False
# )

# FID
seq, flip_angles = fid_tx_adjust.constructor(
    rf_duration=200e-6,
    repetition_time=2,
    n_steps=20,
    adc_duration = 25e-3,
    # flip_angle_range=(pi/4, 3*pi/2),
    flip_angle_range=(np.deg2rad(45), np.deg2rad(270)),
    use_sinc=False
)

# %%
# Larmor frequency:
f_0 = 1965728.0

params = AcquisitionParameter(
    larmor_frequency=f_0,
    # b1_scaling=3.53,
    # b1_scaling=3.054,
    # b1_scaling=3.74,
    b1_scaling=3.56,
    decimation=200,
    # gradient_offset=Dimensions(x=-200, y=0., z=0.)
)

# Perform acquisition
# acq_data: AcquisitionData = acq.run(parameter=params, sequence=seq)
# Run the acquisition
acq.set_sequence(parameter=params, sequence=seq)
acq_data: AcquisitionData = acq.run()

# %%
# FFT
data = np.mean(acq_data.raw, axis=0)[0, ...]
data = np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(data), axis=-1)))

center_window = 100
window_start = int(data.shape[-1]/2-center_window/2)
peak_window = data[:, window_start:window_start+center_window]
peaks = np.sum(data, axis = -1)


def fa_model(samples: np.ndarray, amp: float, step_size: float, phase_offset: float, noise: float) -> np.ndarray:
    """Fit sinusoidal function to measured flip angle values."""
    return amp * np.abs(np.sin(step_size * samples + phase_offset)) + noise

init = [peaks.max(), 1, flip_angles[0], peaks.min()]
fit_params = curve_fit(fa_model, xdata=flip_angles, ydata=peaks, p0=init, method="lm")[0]

fa = np.linspace(flip_angles[0], flip_angles[-1], num=2000)
fit = fa_model(fa, *fit_params)


# Plot
fig, ax = plt.subplots(1, 1, figsize=(10, 6))
ax.scatter(np.degrees(flip_angles), peaks, label="measurement")
ax.plot(np.degrees(fa), fit, label="fit", linestyle="--")
ax.legend()
ax.set_ylabel("Amplitude [a.u.]")
ax.set_xlabel("Flip angle [°]")

# Calculate and print the maximum flip angle corresponding to the peak
flip_angle_max_amp = np.degrees(flip_angles[np.argmax(peaks)])
flip_angle_max_amp_fit = np.degrees(fa[:1000][np.argmax(fit[:1000])])
print("Max. signal at flip angle (measurement): ", flip_angle_max_amp)
print("Max. signal at flip angle (fit): ", flip_angle_max_amp_fit)
factor_meas = flip_angle_max_amp / 90
factor_fit = flip_angle_max_amp_fit / 90
print("B1-scaling factor (meas): ", factor_meas)
print("B1-scaling factor (fit): ", factor_fit)
print("New B1-scaling (meas): ", factor_meas*params.b1_scaling)
print("New B1-scaling (fit): ", factor_fit*params.b1_scaling)
# %%
acq_data.add_info({
    "flip_angles": list(flip_angles),
    "peaks": list(peaks),
})

# %%
acq_data.save(user_path=r"C:\Users\Tom\Desktop\spcm-data\in-vivo", save_unprocessed=True)
# %%
del acq
# %%

