# %%
import json
import os

import matplotlib.pyplot as plt
import numpy as np

# %%
# 1st acquisition == TE1, 2nd acquisition == TE2
acquisitions = [
    r"C:\Users\Tom\Desktop\spcm-data\b0-map\2024-02-15-155826-tse_3d",
    r"C:\Users\Tom\Desktop\spcm-data\b0-map\2024-02-15-160412-tse_3d"
]

meta = []
data = []

for acq in acquisitions:
    _ksp = np.load(os.path.join(acq, "kspace.npy"))
    data.append(_ksp)
    with open(os.path.join(acq, "meta.json"), "rb") as fh:
        _meta = json.load(fh)
        meta.append(_meta)

te_1 = meta[0]["info"]["echo_time"]
te_2 = meta[1]["info"]["echo_time"]

imgs = [np.fft.ifftshift(np.fft.fftn(ksp)).squeeze() for ksp in data]

# %%
idx = 8
slice_1 = imgs[0][idx, ...]
slice_2 = imgs[1][idx, ...]

dim = slice_1.shape
center = [int(x/2) for x in dim]

# phase_correction = np.exp(-1j * slice_1[center[0], center[1]])
phase_correction = 1

phase_1 = np.angle(slice_1*phase_correction)
phase_2 = np.angle(slice_2*phase_correction)

b0map = -(phase_2 - phase_1) / (2*np.pi * (te_2 - te_1))

fig, ax = plt.subplots(1, 1)
ax.imshow(b0map, vmin=-10, vmax=10)
# %%
