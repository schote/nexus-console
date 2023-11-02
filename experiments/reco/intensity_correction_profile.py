# %%
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import decimate

# %%
# Load noise data
noise_data = np.load(
    "/Users/davidschote/Projects/data/2023-11-01-session/2023-11-01-104815-2d_tse_v1/raw_data.npy"
)
data = np.mean(noise_data, axis=0).squeeze()

pe_steps = data.shape[-2]
decimation_factor = int(data.shape[-1]/pe_steps)
ksp = decimate(data, ftype="fir", q=decimation_factor, axis=-1)

print("Decimated k-space shape: ", ksp.shape)

img = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp), axes=(-2, -1)))

fig, ax = plt.subplots(1, 1, figsize=(6, 6))
ax.imshow(np.abs(img), cmap="gray")
ax.set_ylabel("Phase encoding dimension")
ax.set_xlabel("Readout dimension")

# Correction curve
correction = np.std(img, axis=0)

fig, ax = plt.subplots(1, 1, figsize=(6, 4))
ax.plot(correction)
ax.set_ylabel("Intensity correction factor")
ax.set_xlabel("Readout dimension")
ax.grid("on")

# %%
np.save("intensity_correction.npy", correction)

# %%
