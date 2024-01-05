# %%
import matplotlib.pyplot as plt
import numpy as np

from console.spcm_control.ddc import apply_ddc

# %%
# Load acquired SE signal
# filename = "se_signal_05-10-2023"
# raw = np.load(f"/home/schote01/data/spec/{filename}.npy")

# filepath = "../experiments/data_1.txt"
# raw = np.loadtxt(filepath)

raw = np.load("/home/schote01/data/phase_sync/ref_signal/raw_xgrad-0mV.npy")

f_spcm = 20e6   # Spectrum measurement cards sampling frequency; 20 MHz
f_0 = 2.031e6   # Larmorfrequency; 2.031 MHz
num_raw_samples = raw.shape[-1]
adc_duration = num_raw_samples / f_spcm

# %%
# Plot phase of measured signal

_time = (np.arange(num_raw_samples) / num_raw_samples) * adc_duration
fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for k in range(raw.shape[0]):
    ax.plot(_time*1e3, np.degrees(np.angle(raw[k, ...])), label=f"k: {k}")
ax.legend(loc="center left")
ax.set_ylabel("Phase [°]")
ax.set_xlabel("Time [ms]")

# %%
# Reference signal
ref = np.load("/home/schote01/data/phase_sync/ref_signal/ref_xgrad-0mV.npy")

fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for k in range(ref.shape[0]):
    ax.plot(_time*1e3, np.degrees(np.angle(ref[k, ...])), label=f"k: {k}")
ax.legend(loc="center left")
ax.set_ylabel("Phase [°]")
ax.set_xlabel("Time [ms]")

# %%
# Normalized phase

normalized = raw * np.exp(-1j*np.angle(ref))

fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for k in range(normalized.shape[0]):
    ax.plot(_time*1e3, np.degrees(np.angle(normalized[k, ...])), label=f"k: {k}")
ax.legend(loc="center left")
ax.set_ylabel("Phase [°]")
ax.set_xlabel("Time [ms]")




# %%
kernel = 400

filtered = (apply_ddc(raw, kernel, f_0, f_spcm))
filtered_fft = np.fft.fftshift(np.fft.fft(filtered))
fft_freq = np.fft.fftshift(np.fft.fftfreq(filtered_fft.size, kernel/f_spcm))

fig, ax = plt.subplots(1, 1, figsize=(6, 4))
ax.plot(fft_freq, np.abs(filtered_fft), label=f"Kernel size: {kernel}")
ax.set_xlim([-100e3, 100e3])
ax.set_ylabel("Abs. FFT [a.u.]")
ax.legend()
ax.set_xlabel("Frequency [Hz]")

# %%
kernel_size = 200

# Exponential function for demodulation
demod = np.exp(2j*np.pi*f_0*np.arange(kernel_size)/f_spcm)

# Exponential function for resampling
# x = np.arange(kernel_size+1) / (kernel_size/2) - 1
x = np.linspace(-1+1e-16, 1-1e-16, kernel_size)
mixer = np.exp(-1 / (1 - x**2)) * np.sin(x*2.073*np.pi) / x # np.sinc(x * 2.073 * np.pi)

# Integral for normalization
norm = np.sum(mixer)

# Kernel function
kernel = demod * mixer

t_kernel = np.arange(kernel_size) / f_spcm

# Plot kernel
fig, ax = plt.subplots(1, 1, figsize=(6, 4))
ax.plot(t_kernel*1e6, kernel)
ax.plot(t_kernel*1e6, np.abs(kernel), label=f"Kernel size: {kernel_size}")
ax.legend()
ax.set_ylabel("Filter amplitude")
ax.set_xlabel("Time [us]")

# %%
# plot raw
tt = np.arange(raw.size) / f_spcm

fig, ax = plt.subplots(1, 1, figsize=(6, 4))
ax.plot(tt*1e3, raw)
ax.set_xlabel("Time [ms]")
ax.set_ylabel("Amplitude [mV]")
# %%
# Plot filtered time domain
kernel_size = 400

filtered = apply_ddc(raw, kernel_size, f_0, f_spcm)
dwell = filtered.size / f_spcm
fig, ax = plt.subplots(1, 1, figsize=(6, 4))
ax.plot(np.arange(filtered.size)*dwell*1e3, np.abs(filtered), label=f"Kernel size: {kernel_size}")
ax.set_xlabel("Time [ms]")
ax.set_ylabel("Amplitude [mV]")
ax.legend()
# %%
