# %%
import matplotlib.pyplot as plt
from math import log
import numpy as np
import json
from scipy.signal import decimate
from console.spcm_control.ddc import apply_ddc
from console.utilities.snr import snr

import pandas as pd

import numpy as np
from scipy.signal import firwin, lfilter

# %%
# def cic_filter(signal, decimation_factor, number_of_stages):
#     # Convert signal to complex type
#     signal = np.array(signal, dtype=np.complex128)

#     # Integrator Stages
#     for _ in range(number_of_stages):
#         signal = np.cumsum(signal)

#     # Decimation
#     decimated_signal = signal[::decimation_factor]

#     # Comb Stages
#     for _ in range(number_of_stages):
#         delayed_signal = np.zeros_like(decimated_signal, dtype=np.complex128)
#         delayed_signal[1:] = decimated_signal[:-1]
#         decimated_signal = decimated_signal - delayed_signal

#     # Normalization
#     gain = decimation_factor ** number_of_stages
#     normalized_output = decimated_signal / gain

#     return normalized_output

def cic_filter(signal, decimation_factor, number_of_stages):

    # Integrator Stages
    for _ in range(number_of_stages):
        signal = np.cumsum(signal)

    # Decimation
    decimated_signal = signal[::decimation_factor]

    # Comb Stages
    for _ in range(number_of_stages):
        delayed_signal = np.zeros_like(decimated_signal)
        delayed_signal[1:] = decimated_signal[:-1]
        decimated_signal = decimated_signal - delayed_signal

    # Normalization
    gain = np.power(decimation_factor, number_of_stages)
    normalized_output = decimated_signal / gain

    return normalized_output


def decimating_demodulating_fir_filter(signal, sampling_freq, carrier_freq, cutoff, decimation, filter_stage):
    # Demodulation
    demodulated_signal = signal * np.exp(2j * np.pi * np.arange(signal.size) * carrier_freq / sampling_freq)

    nyq_factor = sampling_freq/carrier_freq

    # FIR filter design
    # nyquist_rate = sampling_freq / 2
    # cutoffs = [f / nyquist_rate for f in pass_band]  # Normalize the frequency
    fir_coeff = firwin(numtaps=filter_stage, cutoff=cutoff/nyq_factor, pass_zero=False, fs=sampling_freq, window='hamming')

    # Filtering
    filtered_signal = lfilter(fir_coeff, 1.0, demodulated_signal)

    # Decimation
    # decimated_signal = decimate(filtered_signal, ftype="fir", q=decimation)

    return filtered_signal

# %%

# raw1 = np.load("/home/schote01/spcm-console/2023-11-21-session/2023-11-21-151251-se_spectrum/unprocessed_data.npy")
# raw2 = np.load("/home/schote01/spcm-console/2023-11-21-session/2023-11-21-164611-se_spectrum/unprocessed_data.npy")

# rx_scaling = 200 / (2**15)

# gate_id = 1

# fig, ax = plt.subplots(1, 2, figsize=(8, 4))

# for raw in (raw1, raw2):
#     gate = raw[gate_id, 0, 0, ...]
#     ref = (gate.astype(np.uint16) >> 15).astype(float)
#     sig = (gate << 1).astype(np.int16) * rx_scaling

#     # ax.plot(ref[:50])
#     # ax.plot(np.angle(sig[:1000]))
#     ax[0].plot(sig.real)
#     ax[1].plot(np.angle(sig[:500]))

# fig, ax = plt.subplots(1, 3, figsize=(12, 4))

# for k in range(raw2.shape[0]):
#     # gate = raw1[k, 0, 0, :]
#     gate = raw2[k, 0, 0, :]
#     ref = (gate.astype(np.uint16) >> 15).astype(float)
#     sig = (gate << 1).astype(np.int16) * rx_scaling

#     ax[0].plot(ref[:50])
#     ax[1].plot(sig.real)
#     ax[2].plot(np.angle(sig[:500]))
# %%
# Read data and plot raw signal

raw = np.load("/home/schote01/spcm-console/2023-11-21-session/2023-11-21-151251-se_spectrum/unprocessed_data.npy")

with open("/home/schote01/spcm-console/2023-11-21-session/2023-11-21-151251-se_spectrum/meta.json", "r") as fh:
    meta = json.load(fh)

f_0 = meta["acquisition_parameter"]["larmor_frequency"]
f_spcm = 20e6
rx_scaling = 200 / (2**15)

gate = raw[0, 0, 0, ...]
ref = (gate.astype(np.uint16) >> 15).astype(float)
sig = (gate << 1).astype(np.int16) * rx_scaling

time_axis = np.arange(sig.size) / f_spcm


fig, ax = plt.subplots(1, 1, figsize=(6, 4))
ax.plot(time_axis * 1e3, np.real(sig))
ax.set_ylabel("Amplitude [mV]")
ax.set_xlabel("Time [ms]")

# %%
# Demodulate signal, plot real and imag

demod = np.exp(2j * np.pi * np.arange(gate.size) * f_0 / f_spcm)

sig_demod = sig * demod
# ref_demod = ref * demod

fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].plot(time_axis * 1e3, np.real(sig_demod))
ax[1].plot(time_axis * 1e3, np.imag(sig_demod))
ax[0].set_ylabel("Amplitude [mV]")
ax[0].set_xlabel("Time [ms]")
ax[1].set_xlabel("Time [ms]")
ax[0].set_title("Real")
ax[1].set_title("Imag")


# fig, ax = plt.subplots(1, 3, figsize=(12, 4))
# ax[0].plot(ref_demod[:50])
# ax[1].plot(np.real(sig_demod))
# ax[2].plot(np.angle(sig_demod[:500]))


# %%
# Compare demodulation

decimation = 200

signals_filtered = {
    # "Averaging": apply_ddc(sig, kernel_size=decimation*4, f_0=f_0, f_spcm=f_spcm),
    # "FIR, N=10": 2 * decimate(sig_demod, ftype="fir", q=decimation, n=10),
    # "FIR, N=20": 2 * decimate(sig_demod, ftype="fir", q=decimation, n=20),
    # "FIR, N=30": 2 * decimate(sig_demod, ftype="fir", q=decimation, n=30),
    # "CIC, N=2": 2 * cic_filter(sig_demod, decimation_factor=decimation, number_of_stages=2),
    # "CIC, N=3": 2 * cic_filter(sig_demod, decimation_factor=decimation, number_of_stages=3),
    # "CIC, N=4": 2 * cic_filter(sig_demod, decimation_factor=decimation, number_of_stages=4),
    # "CIC, N=5": 2 * cic_filter(sig_demod, decimation_factor=decimation, number_of_stages=5),
    "FIR, N=20": 2 * decimating_demodulating_fir_filter(sig, 20e6, f_0, 5000 , decimation, 1001)
}

# comparison_snr = {key: snr(_sig) for key, _sig in signals_filtered.items()}

fig, ax = plt.subplots(1, 2, figsize=(12, 4))
for key, _sig in signals_filtered.items():
    ax[0].plot(np.real(_sig))
    ax[1].plot(np.imag(_sig), label=key)

ax[0].set_ylabel("Amplitude [mV]")
ax[0].set_xlabel("Time [ms]")
ax[1].set_xlabel("Time [ms]")
ax[0].set_title("Real")
ax[1].set_title("Imag")
fig.tight_layout(pad=0.2)
ax[1].legend(loc='center left', bbox_to_anchor=(1, 0.5))

# %%
pd.DataFrame().from_dict(
    data={key: [np.std(_sig), np.abs(np.max(_sig))] for key, _sig in signals_filtered.items()},
    orient='index'
)

# %%
