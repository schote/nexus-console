"""
Frequency sweep test sequence for system characterization.

BACKGROUND
----------
Sequence contains of 90 degree RF pulses with gate_duration and a subsequent dead-time of the same duration.
Each RF pulse has a different frequency, depending on the span and the number of frequencies.
The span is devided into num_freqs frequency offsets in the range -span/2 ... +span/2 using linspace.
This leads to a frequency sweep with rectangular RF events, where each event has a unique frequency f_0 + f_offset.
The down-converted data stores all the different frequencies in the phase encoding dimension, since they are acquired by different gates.
The readout dimension should contain a constant value after down-sampling which can be averaged to obtain a value for the sweep with the specific frequency.

PURPOSE
-------
This experiment can be used to check the receive bandwidth of the system

"""
# %%
# imports
import logging

import matplotlib.pyplot as plt
import numpy as np
import sequence_freq_sweep

from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions

# %%
# acquisition control instance
configuration = "../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# construct the sequence
span = 0.4e6
num_freqs = 100
dur = 800e-6
seq, freqs = sequence_freq_sweep.constructor(span=span, num_freqs=num_freqs, gate_duration=dur)

# optional plot:
acq.seq_provider.from_pypulseq(seq)
seq_unrolled = acq.seq_provider.unroll_sequence(larmor_freq=2e6, grad_offset=Dimensions(0, 0, 0))
fig, ax = acq.seq_provider.plot_unrolled()

# %%
# experiment
f_0 = 2.0395e6

params = AcquisitionParameter(
    larmor_frequency=f_0,
    # b1_scaling=4.0,
    b1_scaling=20.0,
    decimation=200,
)

acq.set_sequence(parameter=params, sequence=seq)
acq_data: AcquisitionData = acq.run()
data = np.mean(acq_data.raw, axis=0).squeeze()

# plot result
rx_mean_amp = np.mean(np.abs(data), axis=-1)

fig, ax = plt.subplots(1, 1, figsize=(6, 4))
ax.plot((f_0+freqs)*1e-6, rx_mean_amp)
ax.set_ylabel("Mean RX Amplitude [mV]")
ax.set_xlabel("Frequency [MHz]")


# %%
# save
acq_data.add_info({
    "f_0": f_0,
    "span": span,
    "num_freqs": num_freqs,
    "gate_dur": dur,
    # "note": "direct"
    # "note": "coil"
    # "note": "tr-switch"
    "note": "preamp"
})
acq_data.save(
    user_path="/home/schote01/data/feedback_test/freq_sweep/",
    save_unprocessed=False
)

# %%
del acq
