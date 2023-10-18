# %%
# imports
from console.spcm_control.ddc import apply_ddc
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy.optimize import curve_fit

# %%

raw = np.loadtxt("/home/schote01/data/reference_signal/data_1.txt")

f_spcm = 20e6
f_0 = 2.031e6
kernel_size = 400

filtered = apply_ddc(raw, kernel_size=kernel_size, f_0=f_0, f_spcm=f_spcm)[:-2]

dwell_time = kernel_size / 2 / f_spcm
t_filered = np.arange(filtered.size) * dwell_time

# >> Option 1: Using 1D filter
# b, a = signal.butter(1, 0.3)
# phase_fit = signal.filtfilt(b, a, np.angle(filtered))

# >> Option 2: Polyfit (linear fit)
m_phi, b_phi = np.polyfit(t_filered, np.angle(filtered), 1)
phase_fit = m_phi * t_filered + b_phi
m_amp, b_amp = np.polyfit(t_filered, np.abs(filtered), 1)
amp_fit = m_amp * t_filered + b_amp



fig, ax = plt.subplots(1, 3, figsize=(18, 4))
n_samples_raw = 100
ax[0].plot(1e6 * np.arange(n_samples_raw)/f_spcm, raw[:n_samples_raw])
ax[0].set_ylabel("Raw Signal Amplitude [mV]")
ax[0].set_xlabel("t [us]")

ax[1].plot(1e3 * t_filered, np.abs(filtered), label="Filtered")
ax[1].plot(1e3 * t_filered, amp_fit, label="Linear fit")
ax[1].set_ylabel("Amplitude [mV]")
ax[1].set_ylim([1500, 2500])
ax[1].legend()

ax[2].plot(1e3 * t_filered, np.degrees(np.angle(filtered)), label="Filtered")
ax[2].plot(1e3 * t_filered, np.degrees(phase_fit), label="Linear fit")
ax[2].set_ylabel("Phase [°]")


_ = [a.set_xlabel("t [ms]") for a in ax[1:]]


# %%
# Check amplitudes
y_0 = np.max(raw)
duty_cycle = 0.5
y_eff = np.sqrt(duty_cycle * y_0**2)
y_filt_mean = np.mean(np.abs(filtered))

print(f"Effective amplitude of raw signal: {y_eff} mV")
print(f"Mean amplitude of filtered signal: {y_filt_mean} mV")
# %%
