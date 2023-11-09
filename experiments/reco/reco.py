"""Reconstruction of acquired image data using chambolle-pock algorithm."""
# %%
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import decimate
from console.utilities.reconstruction.chambolle_pock import ChambollePock
from console.utilities.reconstruction.fft_operator import FFTOperator
from skimage.restoration import unwrap_phase
import torch

# %%
session_name = "2023-11-01-session"
# acquisition = "2023-11-01-103607-2d_tse_v1" # without lesion
acquisition = "2023-11-01-110449-2d_tse_v1" # with lesion
# raw_data = np.load(f"/Users/davidschote/Projects/data/{session_name}/{acquisition}/raw_data.npy")
raw_data = np.load(f"/home/schote01/spcm-console/{session_name}/{acquisition}/raw_data.npy")

# Window plot
# scale_vmin = 50 # no averaging
scale_vmin = 100 # with averaging

#%%
# Reconstruction
# Averaging
data = np.mean(raw_data, axis=0).squeeze()
# No averaging
# data = raw_data[0].squeeze()
# data = raw_data.squeeze()

pe_steps = data.shape[-2]
decimation_factor = int(data.shape[-1]/pe_steps)

ksp = decimate(data, ftype="fir", q=decimation_factor, axis=-1)

ksp = np.transpose(ksp)

# ksp = kspace_filter.sine_bell_squared_filter(ksp, filter_strength=0.8)

img = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(ksp), axes=(-2, -1), norm="backward"))

corr = np.load("./intensity_correction.npy")
x = np.arange(corr.size)
corr_poly = np.poly1d(np.polyfit(x=x, y=corr, deg=20))
corr_fit = np.flip(corr_poly(x))[..., None]
# corr_fit = corr_poly(x)[..., None]

img = img / (corr_fit ** 2)

# img = np.sqrt(np.sum(img**2, axis=0).squeeze())

# Plot magnitude image
fig, ax = plt.subplots(1, 1, figsize=(6, 6), dpi=300)
ax.imshow(np.abs(img), cmap="gray", vmin=np.abs(img).min()*scale_vmin, vmax=np.abs(img).max())
ax.axis("off")
fig.set_facecolor("black")

# %%
# Phase unwrapping
# img_transposed = np.transpose(img)

# img_unwrapped = np.unwrap(img, axis=-1)
# img_dc = np.copy(img_transposed)
# unwrapped_phase = unwrap_phase(np.angle(img_dc), wrap_around=(True, False))
# unwrapped_phase = np.pi * unwrapped_phase / unwrapped_phase.max() 
# img_unwrapped = np.abs(img_dc) * np.exp(1j*unwrapped_phase)

# fig, ax = plt.subplots(2, 2)
# fig.colorbar(ax[0, 0].imshow(np.angle(img_transposed), vmin=-np.pi, vmax=np.pi), ax=ax[0, 0])
# fig.colorbar(ax[0, 1].imshow(np.angle(img_unwrapped)), ax=ax[0, 1])
# ax[1, 0].imshow(np.abs(img_transposed), cmap="gray")
# ax[1, 1].imshow(np.abs(img_unwrapped), cmap="gray")
# plt.tight_layout(pad=0.05)

# %%
# TV regularization
ksp_t = torch.tensor(ksp, dtype=torch.cfloat)
img_t = torch.tensor(img, dtype=torch.cfloat)

ft = FFTOperator()
cp = ChambollePock(operator=ft)
img_cp = cp(y=ksp_t, x_0=img_t, num_iterations=200, gamma=0.016)    # without lesions

img_cp_corr = img_cp / (corr_fit ** 2)

fig, ax = plt.subplots(1, 1, figsize=(6, 6), dpi=300)
ax.imshow(img_cp_corr.abs(), cmap="gray", vmin=img_cp_corr.abs().min()*scale_vmin, vmax=img_cp_corr.abs().max())
ax.axis("off")
fig.set_facecolor("black")
plt.tight_layout(pad=0.05)
