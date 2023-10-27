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
# filename = "se_cartesian"
filename = "tse_low-field-scanner_tr1s"

seq_path = f"../sequences/export/{filename}.seq"

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=2036750,
    b1_scaling=7.0, # tSE
    fov_scaling=Dimensions(
        # x=0.01,
        # y=200.,
        # z=20.
        x=40,
        y=40.,
        z=10.,
    ),
    fov_offset=Dimensions(x=0., y=0., z=0.),
    downsampling_rate=200
)

# Perform acquisition
acq.run(parameter=params, sequence=seq_path)

# First argument data from channel 0 and 1,
# second argument contains the phase corrected echo
_, echo_corr = acq.data


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

idx = 0
plt.plot(fft_freq[idx], np.abs(data_fft[idx]))

# %%
# Construct k-space
n_samples = 512
kspace = []

for pe in echo_corr:
    ro_start = int(pe.size/2 - n_samples/2)
    kspace.append(pe[ro_start:ro_start+n_samples])

ksp = np.stack(kspace)

# %%
# ksp = ksp[:4]
plt.imshow(np.abs(ksp), cmap="gray", aspect=ksp.shape[1]/ksp.shape[0])

# %%
# Plot frequency spectrum

fig, ax = plt.subplots(len(data_fft), 1, figsize=(10, 5*len(data_fft)))

for a, _data, _freq in zip(ax, data_fft, fft_freq):
    a.plot(_freq, np.abs(_data))    
    a.set_xlim([-20e3, 20e3])
    a.set_ylim([0, max_spec*1.05])
    a.set_ylabel("Abs. FFT Spectrum [a.u.]")
    
_ = ax[-1].set_xlabel("Frequency [Hz]")


# %%

plot_spcm_data(acq.unrolled_sequence, seq_range=[20e6, 22e6])

# %%
# Delete acquisition control instance to disconnect from cards
del acq

# %%
