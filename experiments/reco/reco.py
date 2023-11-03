# %%
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import decimate
import console.utilities.reconstruction.kspace_filter as kspace_filter

# %%
session_name = "2023-11-01-session"
acquisition = "2023-11-01-103607-2d_tse_v1" # without lesion
# acquisition = "2023-11-01-110449-2d_tse_v1" # with lesion
# raw_data = np.load(f"/Users/davidschote/Projects/data/{session_name}/{acquisition}/raw_data.npy")
raw_data = np.load(f"/home/schote01/spcm-console/{session_name}/{acquisition}/raw_data.npy")

#%%
# Reconstruction
# Averaging
# data = np.mean(raw_data, axis=0).squeeze()
# No averaging
data = raw_data[0].squeeze()

pe_steps = data.shape[-2]
decimation_factor = int(data.shape[-1]/pe_steps)

ksp = decimate(data, ftype="fir", q=decimation_factor, axis=-1)

ksp = kspace_filter.sine_bell_squared_filter(ksp, filter_strength=0.5)

img = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp), axes=(-2, -1)))


corr = np.load("./intensity_correction.npy")
x = np.arange(corr.size)
corr_poly = np.poly1d(np.polyfit(x=x, y=corr, deg=20))
corr_fit = corr_poly(x)

# img = img / corr_fit**2

# Plot magnitude image
fig, ax = plt.subplots(1, 1, figsize=(6, 6), dpi=300)
ax.imshow(np.abs(img), cmap="gray", vmin=np.abs(img).min(), vmax=np.abs(img).max())

# %%
