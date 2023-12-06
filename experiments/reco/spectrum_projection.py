# %%
import numpy as np
import matplotlib.pyplot as plt

# %%
# Load data

# Spectrum
# session_name = "2023-11-01-session"
# acquisition = "2023-11-01-092925-se_spectrum"

# Projection
session_name = "2023-10-31-session"
acquisition = "2023-10-31-111228-se_projection"

raw_data = np.load(f"/home/schote01/spcm-console/{session_name}/{acquisition}/raw_data.npy")

#%%
# FFT
dwell_time = 400/20e6
spectrum = np.fft.fftshift(np.fft.fft(np.fft.fftshift(raw_data), axis=-1, norm="ortho"))
fft_freq = np.fft.fftshift(np.fft.fftfreq(spectrum.shape[-1], dwell_time))


# %%
# Plot phase
fig, ax = plt.subplots(1, 1, figsize=(6, 6))
for k, spec in enumerate(spectrum[:, ...]):
    ax.plot(fft_freq, np.degrees(np.angle(spec[0, 0, :])), label =f"RO {k}")
ax.legend(loc="upper right")
ax.set_xlim([-4e3, 4e3])
ax.set_xlabel("Frequency [Hz]")
ax.set_ylabel("Phase [°]")

# %%
# Plot spectrum
time_ax = np.arange(raw_data.shape[-1]) * dwell_time
spec = spectrum[0, ...].squeeze()

fig, ax = plt.subplots(2, 1, figsize=(6, 6))

ax[0].plot(time_ax*1e3, raw_data.squeeze().real, label="real")
ax[0].plot(time_ax*1e3, raw_data.squeeze().imag, label="imag")
ax[0].plot(time_ax*1e3, np.abs(raw_data.squeeze()), label="absolute")
ax[0].legend(loc="upper right")
ax[0].set_xlabel("Time [ms]")
ax[0].set_ylabel("Amplitude [mV]")

ax[1].plot(fft_freq, np.abs(spectrum[0, ...].squeeze()))
ax[1].set_xlim([-10e3, 10e3])
ax[1].set_ylabel("Magnitude Spectrum [a.u.]")
ax[1].set_xlabel("Frequency [Hz]")

# %%
