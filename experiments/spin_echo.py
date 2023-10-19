"""Execution of a spin echo experiment using the acquisition control."""
# %%
# imports
import numpy as np
import matplotlib.pyplot as plt
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.spcm_control.acquisition_control import AcquistionControl
from console.utilities.spcm_data_plot import plot_spcm_data
from console.spcm_control.ddc import apply_ddc

from scipy.signal import butter, filtfilt

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration)

# %%
# Sequence filename

# filename = "se_spectrum_400us_sinc_8ms-te"
# filename = "se_spectrum_400us_sinc_30ms-te"
# filename = "se_proj_400us-sinc_20ms-te"
# filename = "se_proj_400us_sinc_12ms-te"
# filename = "se_spectrum_200us-rect"


# filename = "se_spectrum_400us_sinc_20ms-te"
filename = "se_spectrum_2500us_sinc_12ms-te"
# filename = "dual-se_spec"


seq_path = f"../sequences/export/{filename}.seq"

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=2032800,
    # b1_scaling=7.0,
    b1_scaling=7.5,
    fov_scaling=Dimensions(x=1., y=1., z=1.),
    fov_offset=Dimensions(x=0., y=0., z=0.),
    downsampling_rate=200
)

# Perform acquisition
acq.run(parameter=params, sequence=seq_path)

# First argument data from channel 0 and 1,
# second argument contains the phase corrected echo
data, echo_corr = acq.data


# %%
data_fft = []
fft_freq = []

# Do FFT
for echo in echo_corr:
    data_fft.append(np.fft.fftshift(np.fft.fft(echo)))
    fft_freq.append(np.fft.fftshift(np.fft.fftfreq(echo.size, acq.dwell_time)))

# Print peak height and center frequency
max_spec = np.max(np.abs(data_fft[0]))
true_f_0 = fft_freq[0][np.argmax(np.abs(data_fft[0]))]

print(f"Frequency offset: {true_f_0} Hz")
print(f"Frequency spectrum max.: {max_spec}")

# %%
# Plot frequency spectrum
fig, ax = plt.subplots(len(data_fft), 1, figsize=(10, 5*len(data_fft)))

if len(data_fft) == 1:
    ax.plot(fft_freq[0], np.abs(data_fft[0]))    
    ax.set_xlim([-20e3, 20e3])
    ax.set_ylim([0, max_spec*1.05])
    ax.set_ylabel("Abs. FFT Spectrum [a.u.]")
    ax.set_xlabel("Frequency [Hz]")
else:
    for a, _data, _freq in zip(ax, data_fft, fft_freq):
        a.plot(_freq, np.abs(_data))    
        a.set_xlim([-20e3, 20e3])
        a.set_ylim([0, max_spec*1.05])
        a.set_ylabel("Abs. FFT Spectrum [a.u.]")
        
    _ = ax[-1].set_xlabel("Frequency [Hz]")


# %%
# Compare phase corrected vs. uncorrected time domain signal:

phase_uncor_1 = np.angle(data[0][0])
phase_uncor_2 = np.angle(data[1][0])

phase_cor_1 = np.angle(echo_corr[0])
phase_cor_2 = np.angle(echo_corr[1])

fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].plot(phase_uncor_1, label="uncorrected")
ax[0].plot(phase_cor_1, label="corrected")
ax[0].legend()

ax[1].plot(phase_uncor_1, label="uncorrected")
ax[1].plot(phase_cor_1, label="corrected")
ax[1].legend()

# %%

plot_spcm_data(acq.unrolled_sequence)

# %%
# Delete acquisition control instance to disconnect from cards
del acq
