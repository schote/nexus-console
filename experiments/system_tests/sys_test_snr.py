# %%
# imports
import logging

import matplotlib.pyplot as plt
import numpy as np

from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter

import sequence_snr


# %%
# acquisition control instance
configuration = "../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
# construct the sequence
# seq = sequence_snr.constructor(rf_duration=200e-6, gate_duration=1e-3)
seq = sequence_snr.constructor(rf_duration=0, gate_duration=2e-3)

# optional plot:
acq.seq_provider.from_pypulseq(seq)
seq_unrolled = acq.seq_provider.unroll_sequence(larmor_freq=2e6)
fig, ax = acq.seq_provider.plot_unrolled()

# %%
# experiment
f_0 = 2.0395e6

params = AcquisitionParameter(
    larmor_frequency=f_0,
    # b1_scaling=4.0,
    b1_scaling=20.0,
    decimation=200,

    # averaging_delay=100e-3,
    # num_averages=50
    # num_averages=2
)

acq.set_sequence(parameter=params, sequence=seq)
acq_data: AcquisitionData = acq.run()
data = np.mean(acq_data.raw, axis=0).squeeze()

# fft
data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(data)))
fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, acq_data.dwell_time))


# plot result
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
# ax.plot(np.arange(data.size)*acq_data.dwell_time*1e3, np.abs(data))
ax[0].plot(np.arange(data.size)*acq_data.dwell_time*1e3, np.real(data), label="Im")
ax[0].plot(np.arange(data.size)*acq_data.dwell_time*1e3, np.imag(data), label="Re")
ax[0].set_ylabel("Amplitude [mV]")
ax[0].set_xlabel("Time [ms]")

ax[1].plot(fft_freq*1e-3, np.abs(data_fft))
ax[1].set_ylabel("Abs. spectrum [a.u.]")
ax[1].set_xlabel("Frequency [kHz]")

std_re = np.std(data.real)
std_im = np.std(data.imag)
std_cp = np.std(data)
# print(f"\nSTANDARD DEVIATION\nre: {std_re}, im: {std_im}")
print(f"\nCOMPLEX STANDARD DEVIATION: {std_cp}")

# unprocessed signal
# plt.plot(acq_data.unprocessed_data[0, 0, 0, :])

# %%
# save
acq_data.add_info({
    "std. re": std_re,
    "std. im": std_im,
    "std. complex": std_cp,
    # "note": "large coil only, shielded room at 3T"
    # "note": "large coil, tr-switch and preamp, shielded room at 3T"
    # "note": "small coil, tr-switch and preamp, shielded room at 3T"
    # "note": "small coil only, shielded room at 3T"
    # "note": "small coil only, outside shielded room at 3T"
    # "note": "small coil, tr-switch and preamp, outside shielded room at 3T"
    # "note": "feed through only, no coil, 50 ohms, shielded room at 3T"
    # "note": "tr-swtch, preamp, feed through, no coil, 50 ohms termination, shielded room at 3T"
    # "note": "tx-rx-test coil only"
    # "note": "rx-rx-test coil + tr-switch"
    # "note": "tx-rx-test coil + tr-switch + wenteq preamp"
    # "note": "tx-rx-test coil + tr-switch + wenteq preamp, outside 3T room"
    # "note": "tx-rx-test coil + tr-switch, outside 3T room"
    "note": "tx-rx-test coil only, outside 3T room"
})
acq_data.save(
    # user_path="/home/schote01/data/noise_characterization/",
    user_path="/home/schote01/data/test/", 
    save_unprocessed=True
)

# %%
del acq
