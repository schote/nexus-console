"""Transmit power calibration (flip angle)."""
# %%
import logging

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

import console.spcm_control.globals as glob
from console.interfaces.interface_acquisition_data import AcquisitionData
from console.spcm_control.acquisition_control import AcquisitionControl
from console.utilities.sequences.calibration import fid_tx_adjust

# %%
configuration = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# FID
seq, flip_angles = fid_tx_adjust.constructor(
    rf_duration=400e-6,
    repetition_time=1,
    n_steps=19,
    adc_duration = 50e-3,
    flip_angle_range=(np.deg2rad(0), np.deg2rad(270)),
    use_sinc=False
)

# %%
# Perform acquisition
acq.set_sequence(sequence=seq)
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

def fa_model_tom(samples: np.ndarray, amp: float, efficiency: float, damping:float, noise: float) -> np.ndarray:
    """Fit sinusoidal function to measured flip angle values."""
    return amp *(1-damping*samples)* np.abs(np.sin(efficiency * samples)) + noise

init = [peaks.max(),1, 0, peaks.min()]
fit_params = curve_fit(fa_model_tom, xdata=flip_angles[:-1], ydata=peaks[:-1], p0=init, method="lm")[0]

fa = np.linspace(flip_angles[0], flip_angles[-1], num=2000)
fit = fa_model_tom(fa, *fit_params)


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
print("New B1-scaling (meas): ", factor_meas*glob.parameter.b1_scaling)
print("New B1-scaling (fit): ", factor_fit*glob.parameter.b1_scaling)

#update global larmor frequency to measured f0
glob.update_parameters(b1_scaling=factor_fit*glob.parameter.b1_scaling)

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

