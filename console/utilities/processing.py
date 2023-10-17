"""Collection of post processing utilities."""

import numpy as np


def window(data: float):
    """Window function for receive data post processing.

    Parameters
    ----------
    data
        Float data sample to window

    Returns
    -------
        Windowed data sample
    """
    # np.pi = 4.0 * np.arctan(1.0)    # ??
    if abs(data) <= 1.0:
        if abs(data) != 0.0:
            wind = np.exp(-1.0 / (1.0 - data * data)) * np.sin(2.073 * np.pi * data) / data
        else:
            wind = np.exp(-1.0 / (1.0 - data * data)) * 2.073 * np.pi
    else:
        wind = 0.0
    return wind


def apply_ddc(raw_signal: np.ndarray, kernel_size: int, f_0: float, f_spcm: float) -> np.ndarray:
    """Apply digital downsampling.

    This function demodulates the raw NMR signal, applies a bandpass filter and does the down-sampling.

    Parameters
    ----------
    raw_signal
        Raw NMR signal in time-domain
    kernel_size
        Filter kernel size
    f_0
        Larmor frequency
    f_spcm
        Sampling frequency

    Returns
    -------
        Filtered and down-sampled signal
    """
    # Exponential function for demodulation
    demod = np.exp(2j * np.pi * f_0 * np.arange(kernel_size) / f_spcm)

    # Exponential function for resampling, don't use [-1, 1] because it leads to a division by zero warning.
    kernel_space = np.linspace(-1 + 1e-15, 1 - 1e-15, kernel_size)
    mixer = np.exp(-1 / (1 - kernel_space**2)) * np.sinc(kernel_space * 2.073 * np.pi)

    # Integral for normalization
    norm = np.sum(mixer)

    # Kernel function
    kernel = demod * mixer

    # Calculate size of down-sampled signal
    num_ddc_samples = raw_signal.size // int(kernel_size / 2)
    signal_filtered = np.zeros(num_ddc_samples, dtype=complex)

    # 1D strided convolution
    for i, k in zip(range(num_ddc_samples), range(0, raw_signal.size, int(kernel_size / 2))):
        # Skip the last samples of the raw signal
        if (position := k + kernel_size) > raw_signal.size:
            # Position in raw data array exceeded index, truncate leftover
            break
        _tmp = np.sum(raw_signal[k:position] * kernel)
        signal_filtered[i] = _tmp * 2 * np.exp(2j * np.pi * f_0 * (k + int(kernel_size / 2)) / f_spcm) / norm

    return signal_filtered
