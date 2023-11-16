"""Digital down converter (DDC) function."""
import numpy as np


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
    kernel_space = np.linspace(-1 + 1e-12, 1 - 1e-12, kernel_size)
    kernel_space[kernel_space == 0] = 1e-12
    mixer = np.exp(-1 / (1 - kernel_space**2)) * np.sin(kernel_space * 2.073 * np.pi) / kernel_space

    # Integral for normalization
    norm = np.sum(mixer)

    # Kernel function
    kernel = demod * mixer

    # Calculate the stride size/overlap, 2 -> half overlap, 4 -> quarter overlap, ...
    stride = 4

    # Calculate size of down-sampled signal
    num_ddc_samples = raw_signal.size // int(kernel_size / stride)
    signal_filtered = np.zeros(num_ddc_samples, dtype=complex)

    # 1D strided convolution
    for i, k in zip(
        range(num_ddc_samples),
        range(0, raw_signal.size, int(kernel_size / stride)),
        strict=True,
    ):
        # Skip the last samples of the raw signal
        if (position := k + kernel_size) > raw_signal.size:
            # Position in raw data array exceeded index, truncate leftover
            break
        # _time = (k + int(kernel_size / stride)) / f_spcm
        _time = k / f_spcm  # time point of window start
        _tmp = np.sum(raw_signal[k:position] * kernel)
        signal_filtered[i] = 2 * _tmp * np.exp(2j * np.pi * f_0 * _time) / norm

    return signal_filtered
