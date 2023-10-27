"""Spin-echo based frequency calibration."""
# %%
# imports
import logging
import numpy as np
import matplotlib.pyplot as plt
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.spcm_control.acquisition_control import AcquistionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.utilities.plot_unrolled_sequence import plot_unrolled_sequence
import console.utilities.sequences as sequences

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration_file=configuration, console_log_level=logging.WARNING, file_log_level=logging.DEBUG)

# %%
# Construct and plot sequence
span = 20e3
seq, f0_offsets = sequences.calibration.se_f0_adjust.constructor(
    freq_span=span, coil_bandwidth=10e3, repetition_time=1000e-3, echo_time=12e-3
)

# Optional:
# acq.seq_provider.from_pypulseq(seq)
# seq_unrolled = acq.seq_provider.unroll_sequence(larmor_freq=2e6, grad_offset=Dimensions(0, 0, 0))
# fig, ax = plot_unrolled_sequence(seq_unrolled)

# %%
# Larmor frequency:
f_0 = 2035029.0

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=2.5,
    adc_samples=200,
    gradient_offset=Dimensions(0, 0, 0),
    num_averages=1,
)

# Perform acquisition
acq_data: AcquisitionData = acq.run(parameter=params, sequence=seq)

# %%
# First argument data from channel 0 and 1,
# second argument contains the phase corrected echo
data = np.mean(acq_data.raw, axis=0)[0].squeeze()

# FFT
data_fft = np.fft.fftshift(np.fft.fft(data))
fft_freq = np.fft.fftshift(np.fft.fftfreq(data.shape[-1], acq_data.dwell_time))

# Calculate center frequency 
max_per_shot = np.max(np.abs(data_fft), axis=-1)
global_max_idx = np.argmax(max_per_shot)
spectrum_max_idx = np.argmax(np.abs(data_fft)[global_max_idx, ...])
max_value = np.max(max_per_shot)

true_f0 = f_0 - fft_freq[spectrum_max_idx]

# Add information to acquisition data
acq_data.add_info({
    "true f0": true_f0,
    "magnitude spectrum max": max_value
})

print(f"True f0 [Hz]: {true_f0}")
print(f"Frequency spectrum max.: {max_value}")
print("Acquisition data shape: ", acq_data.raw.shape)

# %%
# Plot spectra
fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for k, spectrum in enumerate(data_fft[:, ...]):
    ax.plot(fft_freq, np.abs(spectrum))    
ax.set_xlim([-50e3, 50e3])
ax.set_ylim([0, max_value*1.05])
ax.set_ylabel("Abs. FFT Spectrum [a.u.]")
_ = ax.set_xlabel("Frequency [Hz]")


# %%
# Plot the frequency range

offsets = []
spectra = []

fig, ax = plt.subplots(1, 1, figsize=(10, 6))

for k in list(seq.block_events.keys()):
    if (rf_block := seq.get_block(k).rf) is not None and rf_block.use == "excitation":
        offsets.append(rf_block.freq_offset)
        spectra.append(np.fft.ifftshift(np.fft.fft(np.fft.fftshift(rf_block.signal), norm="ortho")))
        
        # Determine frequency axis
        kmax = 0.5 * (1/(rf_block.t[1]-rf_block.t[0]))
        freq = np.linspace(-kmax, kmax, len(spectra[-1])) + offsets[-1]
        
        # Plot pulse magnitude over frequency
        ax.plot(freq*1e-3, np.abs(spectra[-1])*1e-3, label=f"{offsets[-1]/1e3} kHz")
        
ax.set_xlim((-120, 120))
ax.set_ylabel("Excitation B1 [kHz]")
ax.set_xlabel("Frequency [kHz]")
ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

# %%

del acq
# %%
