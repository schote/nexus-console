# %%
# Imports
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# %%
session_name = "2023-11-01-session"
acquisition = "2023-11-01-093257-tx_adjust_fid"

# session_name = "2023-10-31-session"
# acquisition = "2023-10-31-172257-tx_adjust_fid"

raw_data = np.load(f"/home/schote01/spcm-console/{session_name}/{acquisition}/raw_data.npy")

# %%

flip_angles = np.linspace(start=0, stop=5*np.pi/4, num=raw_data.shape[-2], endpoint=True)

data = np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(raw_data.squeeze()), axis=-1)))

center_window = 100
window_start = int(data.shape[-1]/2 - center_window/2)
peak_windows = data[:, window_start:window_start+center_window]
peaks = np.max(peak_windows, axis=-1)

# Truncate
num = 5
peaks = peaks[num:-num]
flip_angles = flip_angles[num:-num]


# Fit sinusoidal function
def fa_model(samples: np.ndarray, amp: float, amp_offset: float, step_size: float, phase_offset: float) -> np.ndarray:
    return amp * np.abs(np.sin(step_size * samples + phase_offset)) + amp_offset

init = [peaks.max(), peaks.min(), 1, flip_angles[0]]
params = curve_fit(fa_model, xdata=flip_angles, ydata=peaks, p0=init, method="lm")[0]

fa = np.linspace(flip_angles[0], flip_angles[-1], num=2000)
fit = fa_model(fa, *params)


# Marker
fa_045_idx = np.argmin(np.abs(fa - 0.25*np.pi))
fa_135_idx = np.argmin(np.abs(fa - 0.75*np.pi))

fa_90_fit_idx = np.argmax(fit[fa_045_idx:fa_135_idx]) + fa_045_idx

fa_90_fit_val = fit[fa_90_fit_idx]
fa_90_fit = fa[fa_90_fit_idx]

fig, ax = plt.subplots(1, 1, figsize=(6, 6), dpi=500)
ax.scatter(np.degrees(flip_angles), peaks, marker="x", label="Measuremet")
ax.plot(np.degrees(fa), fit, label="Curve fit")
# ax.scatter(np.degrees(flip_angles), peaks, marker="x", color="b")
# ax.plot(np.degrees(fa), fit, color="b")
# ax.plot(np.degrees(fa[fa_045_idx:fa_135_idx]), fit[fa_045_idx:fa_135_idx], color="b")

ax.set_ylabel("Amplitude [a.u.]")
ax.set_xlabel("Flip angle [°]")

# ax.vlines(90, peaks.min(), fa_90_fit_val*1.1, colors="r", linestyles="dashed", linewidth=1)
# ax.vlines(np.degrees(fa_90_fit), fa_90_fit_val*0.9, fa_90_fit_val*1.1, colors="r", linewidth=1)
ax.vlines(90, peaks.min(), fa_90_fit_val*1.1, colors="tab:orange", linestyles="dashed", linewidth=1, label="Expected 90°")
ax.vlines(np.degrees(fa_90_fit), fa_90_fit_val*0.9, fa_90_fit_val*1.1, colors="tab:orange", linewidth=1, label="Actual 90°")

ax.text(95, fa_90_fit_val*1.05, f"Deviation: {round(90-np.degrees(fa_90_fit), 2)}°")

ax.legend(loc="upper right")
# %%
