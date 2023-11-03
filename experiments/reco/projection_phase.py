# %%
import numpy as np
import matplotlib.pyplot as plt

# %%
session_name = "2023-10-31-session"
# acquisition = "2023-10-31-111228-se_projection"

raw_data = np.load(f"/home/schote01/spcm-console/{session_name}/{acquisition}/raw_data.npy")

#%%
# Reconstruction
# Averaging
data = np.mean(raw_data, axis=0).squeeze()

spectrum_10 = np.fft.fftshift(np.fft.fft(np.fft.fftshift(data)))
spectrum_1 = np.fft.fftshift(np.fft.fft(np.fft.fftshift(raw_data[0, ...].squeeze())))

fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, 400/20e6))

fig, ax = plt.subplots(1, 1, figsize=(6, 4))
ax.plot(fft_freq, np.abs(spectrum_10))
ax.plot(fft_freq, np.abs(spectrum_1))

# %%
