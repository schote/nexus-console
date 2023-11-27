# %%
import numpy as np
import json
from timeit import timeit
import matplotlib.pyplot as plt
from scipy.signal import decimate, firwin, convolve, lfilter
from console.utilities.snr import signal_to_noise_ratio

import pandas as pd

# %%
def filter_cic(signal, decimation, number_of_stages):
    # Integrator Stages
    for _ in range(number_of_stages):
        signal = np.cumsum(signal)
    # Decimation
    decimated_signal = signal[::decimation]
    # Comb Stages
    for _ in range(number_of_stages):
        delayed_signal = np.zeros_like(decimated_signal)
        delayed_signal[1:] = decimated_signal[:-1]
        decimated_signal = decimated_signal - delayed_signal
    # Normalization
    gain = np.power(decimation, number_of_stages)
    return decimated_signal / gain

def filter_cic_fir_comp(signal, decimation, number_of_stages):
    if not (cic_decimation := decimation / 2).is_integer():
        raise ValueError("Decimation factor must be even.")

    # Integrator Stages
    for _ in range(number_of_stages):
        signal = np.cumsum(signal)

    # Decimation
    decimated_signal = signal[::int(cic_decimation)]

    # Comb Stages
    for _ in range(number_of_stages):
        delayed_signal = np.zeros_like(decimated_signal)
        delayed_signal[1:] = decimated_signal[:-1]
        decimated_signal = decimated_signal - delayed_signal

    # Normalization
    gain = np.power(cic_decimation, number_of_stages)
    decimated_signal = decimated_signal / gain

    return decimate(x=decimated_signal, q=2, ftype="fir")


def filter_moving_average(signal, decimation: int = 100, overlap: int = 4):
    # Calculate kernel size
    kernel_size = int(overlap * decimation)
    # Exponential function for resampling
    # To prevent division by zero for [-1, 1, 0], noise at the scale of 1e-20 is added
    kernel_space = np.linspace(-1, 1, kernel_size) + np.random.rand(kernel_size) * 1e-20
    # Define kernel
    kernel = np.exp(-1 / (1 - kernel_space**2)) * np.sin(kernel_space * 2.073 * np.pi) / kernel_space
    # Integral for normalization
    norm = np.sum(kernel)

    # Calculate size of down-sampled signal
    num_ddc_samples = signal.shape[-1] // decimation
    signal_filtered = np.zeros(signal.shape[:-1] + (num_ddc_samples, ), dtype=complex)

    # Zero-padding of signal to center down-sampled signal

    n_pad = [(0, 0)] * signal.ndim
    n_pad[-1] = (int(overlap * decimation / 2), ) * 2
    signal_pad = np.pad(signal, pad_width=n_pad, mode="constant", constant_values=[0])

    # 1D strided convolution
    for k in range(num_ddc_samples):
        # _tmp = np.sum(signal_pad[..., k * decimation : k * decimation + kernel_size] * kernel)
        _tmp = signal_pad[..., k * decimation : k * decimation + kernel_size] @ kernel
        signal_filtered[..., k] = 2 * _tmp / norm
    return signal_filtered


def filter_moving_average_rect(signal, decimation: int = 100, overlap: int = 4):
    # Calculate kernel size
    kernel_size = int(overlap * decimation)
    # Calculate size of down-sampled signal
    num_ddc_samples = signal.shape[-1] // decimation
    signal_filtered = np.zeros(signal.shape[:-1] + (num_ddc_samples, ), dtype=complex)
    # Zero-padding of signal to center down-sampled signal
    signal_pad = np.pad(signal, pad_width=int(overlap * decimation / 2), mode="constant", constant_values=[0])
    # 1D strided convolution
    for k in range(num_ddc_samples):
        signal_filtered[k] = 2 * np.sum(signal_pad[k * decimation : k * decimation + kernel_size]) / kernel_size
    return signal_filtered


def filter_fir(signal, decimation: int | list[int]):
    if not isinstance(decimation, list):
        decimation = [decimation]
    for dec in decimation:
        signal = decimate(signal, q=dec, ftype="fir")
    return signal

# def filter_fir2(signal, order: int = 100, cutoff: float = 0.1):
#     a = firwin(order+1, cutoff=cutoff, window="hamming", pass_zero="lowpass")
#     return lfilter(a, 1.0, signal)


# %%
# Load data
raw = np.load("/home/schote01/spcm-console/2023-11-21-session/2023-11-21-151251-se_spectrum/unprocessed_data.npy")

with open("/home/schote01/spcm-console/2023-11-21-session/2023-11-21-151251-se_spectrum/meta.json", "r") as fh:
    meta = json.load(fh)

f_0 = meta["acquisition_parameter"]["larmor_frequency"]
f_spcm = 20e6
rx_scaling = 200 / (2**15)

# Separate raw and reference signals
gate = raw[0, 0, 0, ...]
ref = (gate.astype(np.uint16) >> 15).astype(float)
sig = (gate << 1).astype(np.int16) * rx_scaling

time_axis = np.arange(sig.size) / f_spcm

# fig, ax = plt.subplots(1, 1, figsize=(6, 4))
# ax.plot(time_axis * 1e3, sig)
# ax.set_ylabel("Amplitude [mV]")
# ax.set_xlabel("Time [ms]")

# Demodulation
sig = sig * np.exp(2j * np.pi * np.arange(gate.size) * f_0 / f_spcm)

# ax[1].plot(time_axis * 1e3, np.abs(sig))
# ax[1].set_xlabel("Time [ms]")


# %%
# Comparison of filters

decimation = 100

comparison = {
    "Moving Average": filter_moving_average(sig[None, None, ...], decimation=decimation, overlap=4),
    "Moving Average Rect": filter_moving_average_rect(sig, decimation=decimation, overlap=4),
    "CIC": filter_cic(sig, decimation=decimation, number_of_stages=5),
    "CIC Compensated": filter_cic_fir_comp(sig, decimation=decimation, number_of_stages=5),
    "FIR": filter_fir(signal=sig, decimation=decimation),
    "Multistage FIR": filter_fir(signal=sig, decimation=[2, 2, 5, 5])
}

comparison_fft = {key: 20 * np.log(np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(data))))) for key, data in comparison.items()}
comparison_snr = {key: signal_to_noise_ratio(data) for key, data in comparison.items()}
comparison_snr_rms = {key: signal_to_noise_ratio(data, use_rms=True) for key, data in comparison.items()}

freq_axis = np.fft.fftshift(np.fft.fftfreq(int(sig.size/decimation), decimation / f_spcm))

for k, (key, data) in enumerate(comparison_fft.items()):
    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    ax.plot(freq_axis, np.abs(np.squeeze(data)))
    ax.set_title(key)
    ax.set_ylabel("Abs. Spectrum [dB]")
    ax.set_xlabel("Frequency [Hz]")
    ax.set_yscale("log")
    ax.grid("on")
    ax.set_ylim([1e-1, 2e2])


pd.DataFrame().from_dict(
    data={key: [comparison_snr[key], comparison_snr_rms[key]] for key in comparison_snr.keys()},
    orient='index'
)


# %%
# Measure performance

comparison_calls = {
    "Moving Average": "filter_moving_average(sig, decimation=decimation, overlap=4)",
    "Moving Average Rect": "filter_moving_average_rect(sig, decimation=decimation, overlap=4)",
    "CIC": "filter_cic(sig, decimation=decimation, number_of_stages=5)",
    "CIC Compensated": "filter_cic_fir_comp(sig, decimation=decimation, number_of_stages=5)",
    "FIR": "filter_fir(signal=sig, decimation=decimation)",
    "Multistage FIR": "filter_fir(signal=sig, decimation=[2, 2, 5, 5])"
}

durations = {}
n_calls = 1000

for key, call in comparison_calls.items():
    durations[key] = timeit(call, number=n_calls, globals=globals())

pd.DataFrame().from_dict(data=durations, orient='index')


# %%
# # Comparison of filters, TODO: Double-check this evaluation...

# impulse = np.zeros_like(sig)
# center = int(sig.size / 2) + 1
# impulse[center] = 1 - 1j
# # impulse[0] = 1

# comparison = {
#     "Moving Average": filter_moving_average(impulse, decimation=decimation, overlap=4),
#     "Moving Average Rect": filter_moving_average_std(impulse, decimation=decimation, overlap=4),
#     "CIC": filter_cic(impulse, decimation=decimation, number_of_stages=5),
#     "CIC Compensated": filter_cic_fir_comp(impulse, decimation=decimation, number_of_stages=5),
#     "FIR": filter_fir(signal=impulse, decimation=decimation),
#     "Multistage FIR": filter_fir(signal=impulse, decimation=[2, 2, 5, 5])
# }

# comparison_fft_impulse = {key: 20 * np.log10(np.abs(np.fft.fft(data))) for key, data in comparison.items()}

# for k, (key, data) in enumerate(comparison_fft_impulse.items()):
#     fig, ax = plt.subplots(1, 1, figsize=(9, 5))
#     ax.plot(freq_axis, data)
#     ax.set_title(key)
#     ax.set_ylabel("Abs. Spectrum [dB]")
#     ax.set_xlabel("Frequency [Hz]")
#     ax.set_yscale("log")
#     ax.grid("on")
# %%
# Reference signal

comparison_ref = {
    "Moving Average": filter_moving_average(ref, decimation=decimation, overlap=4),
    "Moving Average Rect": filter_moving_average_rect(ref, decimation=decimation, overlap=4),
    "CIC": filter_cic(ref, decimation=decimation, number_of_stages=5),
    "CIC Compensated": filter_cic_fir_comp(ref, decimation=decimation, number_of_stages=5),
    "FIR": filter_fir(signal=ref, decimation=decimation),
    "Multistage FIR": filter_fir(signal=ref, decimation=[2, 2, 5, 5])
}

time_axis = np.arange(int(sig.size/decimation)) * (decimation / f_spcm)

fig, ax = plt.subplots(1, 1, figsize=(6, 4))
for key, data in comparison_ref.items():
    ax.plot(time_axis*1e3, np.degrees(np.angle(data)), label=key)
    ax.set_xlabel("Time [ms]")
    ax.set_ylabel("Phase reference [°]")
fig.legend()

# %%
