# %%
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import decimate
import console.utilities.reconstruction.kspace_filter as kspace_filter

from console.spcm_control.ddc import apply_ddc
# %%
# Load data

session_name = "2023-11-01-session"
# acquisition = "2023-11-01-103607-2d_tse_v1" # without lesion
acquisition = "2023-11-01-110449-2d_tse_v1"

raw_data = np.load(f"/home/schote01/spcm-console/{session_name}/{acquisition}/unprocessed_data_array.npy")

# %%
# DDC

f_0 = 1964390.0
decimation_rate = 200

n_ro = 512
n_pe = raw_data.shape[-2]
n_avg = raw_data.shape[0]
ksp = np.zeros((n_avg, n_pe, n_ro), dtype=complex)

for k_avg in range(n_avg):
    for k_pe in range(n_pe):
        # Apply ddc
        _ref = apply_ddc(raw_signal=raw_data[k_avg, 0, k_pe, :], kernel_size=int(2*decimation_rate), f_0=f_0, f_spcm=20e6)
        _ksp = apply_ddc(raw_signal=raw_data[k_avg, 1, k_pe, :], kernel_size=int(2*decimation_rate), f_0=f_0, f_spcm=20e6)
        # Truncate data
        win_0 = int(_ref.size/2 - n_ro/2)
        _ref = _ref[win_0:win_0+n_ro]
        _ksp = _ksp[win_0:win_0+n_ro]
        # Phase correction
        ksp[k_avg, k_pe, :] = _ksp * np.exp(-1j * np.angle(_ref))
        
# img = np.fft.fftshift(np.fft.fftn(np.fft.fftshift(ksp), axes=(-2, -1)))
# %%
# 2nd stage down sampling

decimation_factor = int(ksp.shape[-1]/n_pe)
ksp_dec = decimate(ksp, ftype="fir", q=decimation_factor, axis=-1)

img = np.fft.fftshift(np.fft.fft2(np.fft.fftshift(np.mean(ksp_dec, axis=0))))

fig, ax = plt.subplots(1, 1, figsize=(6, 6))
ax.imshow(np.abs(img), cmap="gray")

# %%
