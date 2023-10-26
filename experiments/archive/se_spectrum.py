"""Execution of a spin echo experiment using the acquisition control."""
# %%
# imports
import logging
import numpy as np
import matplotlib.pyplot as plt
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.spcm_control.acquisition_control import AcquistionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.utilities.plot_unrolled_sequence import plot_unrolled_sequence

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration_file=configuration, file_log_level=logging.DEBUG)

# %%
# Sequence filename

# filename = "se_spectrum_400us_sinc_8ms-te"
# filename = "se_spectrum_400us_sinc_30ms-te"
# filename = "se_proj_400us-sinc_20ms-te"
filename = "se_proj_400us_sinc_12ms-te"
# filename = "se_spectrum_200us-rect"
# filename = "se_spectrum_400us_sinc_20ms-te"
# filename = "se_spectrum_2500us_sinc_12ms-te"
# filename = "dual-se_spec"

f_0 = 2037729.6875

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=2.5,
    # b1_scaling=7.0,
    fov_scaling=Dimensions(
        # x=5.,
        x=0.6,
        y=0., 
        z=0.
    ),
    fov_offset=Dimensions(x=0., y=0., z=0.),
    downsampling_rate=400,
    adc_samples=500,
    num_averages=1,
)

# Perform acquisition
acq_data: AcquisitionData = acq.run(parameter=params, sequence=f"../sequences/export/{filename}.seq")



# First argument data from channel 0 and 1,
# second argument contains the phase corrected echo
data = np.mean(acq_data.raw, axis=0).squeeze()


data_fft = np.fft.fftshift(np.fft.fft(data))
fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, acq_data.dwell_time))

# Print peak height and center frequency
max_spec = np.max(np.abs(data_fft))
f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]

print("\nRF max. [mv]: ", 200*np.max(np.concatenate(acq.unrolled_sequence.seq)[0::4])/np.iinfo(np.int16).max)
print(f"Frequency offset [Hz]: {f_0_offset}, new frequency f0 [Hz]: {f_0 - f_0_offset}")
print(f"Frequency spectrum max.: {max_spec}")
print("Acquisition data shape: ", acq_data.raw.shape)

# acq_data.write()

# %%
# Plot frequency spectrum
fig, ax = plt.subplots(1, 1, figsize=(10, 5))
ax.plot(fft_freq, np.abs(data_fft))    
ax.set_xlim([-20e3, 20e3])
ax.set_ylim([0, max_spec*1.05])
ax.set_ylabel("Abs. FFT Spectrum [a.u.]")
_ = ax.set_xlabel("Frequency [Hz]")

# %%
# Plot sequence
fig, ax = plot_unrolled_sequence(acq.unrolled_sequence)

# %%
fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for d in acq_data.raw.squeeze()[:, ...]:
    ax.plot(np.degrees(np.angle(d)))


# %%
# Delete acquisition control instance to disconnect from cards
del acq
