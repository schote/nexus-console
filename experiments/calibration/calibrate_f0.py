"""Spin-echo spectrum."""
# %%
import logging

import matplotlib.pyplot as plt
import numpy as np

from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter
from console.utilities.sequences.spectrometry import se_spectrum
from console.utilities.snr import signal_to_noise_ratio

# %%
# Create acquisition control instance
configuration = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# Spinecho
seq = se_spectrum.constructor(
    echo_time=12e-3,
    rf_duration=100e-6,
    time_bw_product=0,
    use_sinc=False
)

# Optional:
# acq.seq_provider.from_pypulseq(seq)
# seq_unrolled = acq.seq_provider.unroll_sequence(larmor_freq=2e6, grad_offset=Dimensions(0, 0, 0))
# fig, ax = acq.seq_provider.plot_unrolled()

# %%
# Larmor frequency:
f_0 = 2039250.0

params = AcquisitionParameter(
    larmor_frequency=f_0,
    b1_scaling=2.3,
    num_averages=1,
)

acq.set_sequence(parameter=params, sequence=seq)
acq_data: AcquisitionData = acq.run()

# FFT
data = np.mean(acq_data.raw, axis=0)[0].squeeze()
data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(data)))
fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, acq_data.dwell_time))

max_spec = np.max(np.abs(data_fft))
f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]

snr = signal_to_noise_ratio(data_fft, dwell_time=acq_data.dwell_time)

# Add information to acquisition data
acq_data.add_info({
    "time_bw_product": seq.get_definition("time_bw_product"),
    "rf_duration": seq.get_definition("rf_duration"),
    "pulse_type": seq.get_definition("pulse_type"),
    "true f0": f_0 - f_0_offset,
    "magnitude spectrum max": max_spec,
    "snr dB": snr,
})

print(f"Frequency offset [Hz]: {f_0_offset}\nNew frequency f0 [Hz]: {f_0 - f_0_offset}")
print(f"Frequency spectrum max.: {max_spec}")
print("Acquisition data shape: ", acq_data.raw.shape)
print("SNR [dB]: ", snr)

# Plot spectrum
fig, ax = plt.subplots(1, 1, figsize=(10, 5))
ax.plot(fft_freq, np.abs(data_fft))
# ax.set_xlim([-20e3, 20e3])
ax.set_ylim([0, max_spec * 1.05])
ax.set_ylabel("Abs. FFT Spectrum [a.u.]")
ax.set_xlabel("Frequency [Hz]")
plt.show()

# %%
# Save acquisition data
acq_data.save(save_unprocessed=False)

# %%