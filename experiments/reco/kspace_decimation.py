# %%
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import decimate

# %%
# Load image data
session_name = "2023-11-01-session"
acquisition = "2023-11-01-103607-2d_tse_v1"
raw_data = np.load(f"/Users/davidschote/Projects/data/{session_name}/{acquisition}/raw_data.npy")

# %%
# Compare decimation filters
data = np.mean(raw_data, axis=0).squeeze()
pe_steps = data.shape[-2]
decimation_factor = int(data.shape[-1]/pe_steps)

ksp_fir = decimate(data, ftype="fir", q=decimation_factor, axis=-1)
ksp_iir = decimate(data, ftype="iir", q=decimation_factor, axis=-1)

img_fir = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp_fir), axes=(-2, -1)))
img_iir = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp_iir), axes=(-2, -1)))

fig, ax = plt.subplots(1, 2, figsize=(10, 5))
abs_min = np.abs(img_fir).min()
abs_max = np.abs(img_fir).max()
ax[0].imshow(np.abs(img_fir), cmap="gray", vmin=abs_min, vmax=abs_max)
ax[1].imshow(np.abs(img_iir), cmap="gray", vmin=abs_min, vmax=abs_max)
_ = ax[0].set_title("FIR")
_ = ax[1].set_title("IIR")

# %%
# Intensity correction
corr = np.load("./intensity_correction.npy")
x = np.arange(corr.size)
corr_poly = np.poly1d(np.polyfit(x=x, y=corr, deg=30))
corr_fit = corr_poly(x)

# Plot intensity correction profile
fig, ax = plt.subplots(1, 1, figsize=(6, 4))
ax.plot(corr, label="Noise std. dev.")
ax.plot(corr_fit, label="Polynomial fit")
ax.set_ylabel("Intensity profile")
ax.set_xlabel("Readout dimension")
ax.legend()

# Correction after averaging
img_corr = img_fir / corr_fit

# Correction before averaging:
ksp_fir_pre = decimate(raw_data.squeeze(), ftype="fir", q=decimation_factor, axis=-1)
img_fir_pre = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp_fir_pre), axes=(-2, -1)))
img_corr_pre = np.mean(img_fir_pre[..., :] / corr_fit, axis=0)

# Plotting
fig, ax = plt.subplots(1, 3, figsize=(15, 5))
ax[0].imshow(np.abs(img_fir), cmap="gray")
ax[1].imshow(np.abs(img_corr), cmap="gray")
ax[2].imshow(np.abs(img_corr_pre), cmap="gray")
_ = ax[0].set_title("Uncorrected Intensity")
_ = ax[1].set_title("Corrected Intensity")
_ = ax[2].set_title("Corrected Intensity Before Averaging")

# %%
