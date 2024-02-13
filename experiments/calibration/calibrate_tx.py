"""Transmit power calibration (flip angle)."""
# %%
import logging
from math import pi

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter
from console.utilities.sequences.calibration import se_tx_adjust

# %%
configuration = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Spinecho
seq, flip_angles = se_tx_adjust.constructor(
    echo_time=12e-3,
    rf_duration=200e-6,
    repetition_time=2,
    n_steps=10,
    # flip_angle_range=(pi/4, 3*pi/2),
    flip_angle_range=(pi/4, 3*pi/4),
    use_sinc=False
)

# FID
# seq, flip_angles = fid_tx_adjust.constructor(
#     rf_duration=200e-6, repetition_time = 4,
#     n_steps=50,
#     flip_angle_range=(pi/4, 3*pi/2),
#     pulse_type="block"
#     )

# %%
# Larmor frequency:
f_0 = 2039250.0

params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=2.51,
    decimation=200,
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
peaks = np.max(peak_window, axis=-1)


def fa_model(samples: np.ndarray, amp: float, amp_offset: float, step_size: float, phase_offset: float) -> np.ndarray:
    """Fit sinusoidal function to measured flip angle values."""
    return amp * np.abs(np.sin(step_size * samples + phase_offset)) + amp_offset

init = [peaks.max(), peaks.min(), 1, flip_angles[0]]
params = curve_fit(fa_model, xdata=flip_angles, ydata=peaks, p0=init, method="lm")[0]

fa = np.linspace(flip_angles[0], flip_angles[-1], num=2000)
fit = fa_model(fa, *params)


# Plot
fig, ax = plt.subplots(1, 1, figsize=(10, 6))
ax.scatter(np.degrees(flip_angles), peaks, label="measurement")
ax.plot(np.degrees(fa), fit, label="fit")
ax.legend()
ax.set_ylabel("Amplitude [a.u.]")
ax.set_xlabel("Flip angle [°]")

# Calculate and print the maximum flip angle corresponding to the peak
flip_angle_max_amp = np.degrees(flip_angles[np.argmax(peaks)])
flip_angle_max_amp_fit = np.degrees(fa[np.argmax(fit)])
print("Max. signal at flip angle (measurement): ", flip_angle_max_amp)
print("Max. signal at flip angle (fit): ", )
factor = flip_angle_max_amp_fit / 90
print("Scale B1 by: ", factor)

# %%
acq_data.add_info({
    "flip_angles": list(flip_angles),
    "peaks": list(peaks),
})

# %%
acq_data.save(save_unprocessed=False)
# %%
del acq
# %%

