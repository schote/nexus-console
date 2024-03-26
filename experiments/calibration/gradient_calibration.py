# %%
import sequence_gradint_calibration
import logging

from console.spcm_control.acquisition_control import AcquisitionControl
import matplotlib.pyplot as plt

# %%

configuration_file = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration_file, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
seq = sequence_gradint_calibration.constructor(
    fov=0.24,
    num_samples=120,
    ramp_duration=200e-6,
    ro_bandwidth=20e3,
    delay=10e-3,
    post_gradient_adc_duration=0.5e-3
)
seq.plot()

# %%
acq.set_sequence(seq)
# acq.seq_provider.plot_unrolled()
acq_data = acq.run()

# %%




from console.pulseq_interpreter.sequence_provider import SequenceProvider
import pypulseq as pp
import numpy as np
import matplotlib.pyplot as plt

import os
import json

# %%

experiment = os.path.join("/Volumes/T7-Data/spcm-data_25-03-24/gradient-calibration/2024-03-25-171011-grad-calibration", "")

with open(os.path.join(experiment, "meta.json")) as fh:
    meta = json.load(fh)


# Create sequence provider
provider = SequenceProvider(
    # gpa_gain=[8.35, 8.35, 8.35],
    # gradient_efficiency=[0.37e-3, 0.451e-3, 0.4e-3],
    # output_limits=[200, 6000, 6000, 6000],
    gpa_gain=meta["SequenceProvider"]["gpa_gain"],
    gradient_efficiency=meta["SequenceProvider"]["gradient_efficiency"],
    output_limits=meta["SequenceProvider"]["output_limits"],
    high_impedance=[False, False, False, False] # dont scale by 0.5 -> set gradients to false
)

# Loada sequence
seq = pp.Sequence()
seq.read(os.path.join(experiment, "sequence.seq"))

# Set sequence and unroll
provider.from_pypulseq(seq)
unrolled_seq = provider.unroll_sequence()
# %%
# Load data
data = np.load(os.path.join(experiment, "unprocessed_data.npy"))
monitor = data[0, 1, 0, ...]

channel_id = 1
rx_scaling = meta["RxCard"]["rx_scaling"][channel_id]
offset = meta["acquisition_parameter"]["gradient_offset"]["x"]

# Get x-Gradient ideal waveform
waveform = unrolled_seq.seq[1][channel_id::4]
# Transform to volts
# waveform = (np.uint16(waveform) << 1).astype(np.int16) / (2**15) * provider.output_limits[channel_id]
waveform = waveform.astype(np.int16) * rx_scaling

# Truncate monitor: Sequence contains dead-time at the end which is not part of the adc gate
# However, ADC and gradient start without delay
waveform = waveform[:monitor.size] + offset


# Time axis
time_ax = np.arange(waveform.size) * provider.spcm_dwell_time

# %%
# Plot

fig, ax = plt.subplots(1, 1)
ax.plot(time_ax, -monitor)
ax.plot(time_ax, waveform)

# TODO: Check offset and FOV scaling
gradient_data = acq_data.unprocessed_data[0][0, 1, 0, ...]
plt.plot(gradient_data)


# %%

acq_data.save(user_path=r"C:\Users\Tom\Desktop\spcm-data_25-03-24\gradient-calibration", save_unprocessed=True)
# %%
