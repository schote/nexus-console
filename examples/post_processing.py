# %%
import numpy as np
import matplotlib.pyplot as plt
from console.utilities.processing import apply_ddc

# %%
# Load acquired SE signal
filename = "se_signal_05-10-2023"
filename = ""

raw = np.load(f"data/{filename}.npy")

f_spcm = 20e6   # Spectrum measurement cards sampling frequency; 20 MHz
f_0 = 2.031e6   # Larmorfrequency; 2.031 MHz
num_raw_samples = raw.size
adc_duration = num_raw_samples / f_spcm


# %%
kernels = list(range(100, 900, 100))

fig, ax = plt.subplots(len(kernels), 1, figsize=(10, 15))

for i, kernel in enumerate(kernels):
    filtered = (apply_ddc(raw, kernel, f_0, f_spcm))
    filtered_fft = np.fft.fftshift(np.fft.fft(filtered))
    fft_freq = np.fft.fftshift(np.fft.fftfreq(filtered_fft.size, kernel/f_spcm))
    ax[i].plot(fft_freq, np.abs(filtered_fft), label=f"Kernel size: {kernel}")
    ax[i].set_xlim([-100e3, 100e3])
    ax[i].set_ylabel("Abs. FFT [a.u.]")
    ax[i].legend()
ax[-1].set_xlabel("Frequency [Hz]")

# %%
kernel_size = 600

# Exponential function for demodulation
demod = np.exp(2j*np.pi*f_0*np.arange(kernel_size)/f_spcm)

# Exponential function for resampling
x = np.linspace(-1, 1, kernel_size)
mixer = np.exp(-1 / (1 - x**2)) * np.sinc(x * 2.073 * np.pi)

# Integral for normalization
norm = np.sum(mixer)

# Kernel function
kernel = demod * mixer

fig, ax = plt.subplots(1, 3, figsize=(15, 3))
ax[0].plot(x, kernel)
ax[0].plot(x, np.abs(kernel), label=f"Kernel size: {kernel_size}")
ax[0].legend()

kernel_fft = np.fft.fftshift(np.fft.fft(kernel))
fft_freq = np.fft.fftshift(np.fft.fftfreq(kernel.size, 1/f_spcm))

ax[1].plot(fft_freq, np.abs(kernel_fft))
ax[2].plot(fft_freq, np.abs(kernel_fft))
ax[2].set_xlim([f_0-1e6, f_0+1e6])

ax[1].set_xlabel("Frequency [Hz]")
ax[2].set_xlabel("Frequency [Hz]")
ax[0].set_title("Time domain")
ax[1].set_title("Frequency domain")
ax[2].set_title("Frequency domain")
# %%
