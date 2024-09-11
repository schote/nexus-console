"""Digital down converter (DDC) function."""
import numpy as np
from scipy.signal import decimate


def filter_moving_average(signal, decimation: int = 100, overlap: int = 8):
    r"""Decimate data using a moving average filter.

    $kernel = e^{\frac{-1}{1 - x^2}} * \sin{2.073 * \pi \ x} / x, \; x = -1, ..., 1$

    Parameters
    ----------
    signal
        Unprocessed raw signal to be decimated and filtered.
        Input signal shape is supposed to be [averages, coils, phase encoding, readout].
        Downsampling is applied to the readout dimension.
    decimation, optional
        Decimation factor, by default 100
    overlap, optional
        Overlap factor of the kernel.
        If 2, kernel is applied every kernel_size/2, if 4 every kerne_size/4 and so on.
        By default 4

    Returns
    -------
        Downsampled signal
    """
    # Calculate kernel size
    kernel_size = int(overlap * decimation)
    # Exponential function for resampling
    # To prevent division by zero for [-1, 1, 0], noise at the scale of 1e-20 is added
    # kernel_noise = np.random.choice(list(range(-9, 0)) + list(range(1, 10)), kernel_size) * 1e-3
    kernel_space = np.linspace(-1 + 1e-10, 1 - 1e-10, kernel_size)
    kernel_space[kernel_space == 0] = 1e-10
    # Define kernel
    kernel = np.exp(-1 / (1 - kernel_space**2)) * np.sin(kernel_space * 2.073 * np.pi) / kernel_space
    # Integral for normalization
    norm = np.sum(kernel)

    # Calculate size of down-sampled signal
    # num_ddc_samples = signal.shape[-1] // decimation
    num_ddc_samples = round(signal.shape[-1] / decimation)
    signal_filtered = np.zeros(signal.shape[:-1] + (num_ddc_samples,), dtype=complex)

    # Zero-padding of signal to center down-sampled signal

    n_pad = [(0, 0)] * signal.ndim
    n_pad[-1] = (int(overlap * decimation / 2),) * 2
    signal_pad = np.pad(signal, pad_width=n_pad, mode="constant", constant_values=[0])

    # 1D strided convolution
    for k in range(num_ddc_samples):
        # _tmp = np.sum(signal_pad[..., k * decimation : k * decimation + kernel_size] * kernel)
        _tmp = signal_pad[..., k * decimation : k * decimation + kernel_size] @ kernel
        signal_filtered[..., k] = 2 * _tmp / norm
    return signal_filtered


def filter_cic_fir_comp(signal, decimation, number_of_stages):
    """Decimate data using CIC filter and FIR compensation.

    Two stage decimation:
    (1) CIC decimation by decimation/2 rate
    (2) FIR decimation by factor 2

    The signal size after decimation can be determined by
    >>> signal.shape[-1] // decimation

    The number of decimated samples after the first stage depends output sample size.
    Any left over samples in CIC decimation stage are truncated.

    Parameters
    ----------
    signal
        Unprocessed raw signal to be decimated and filtered.
        Input signal shape is supposed to be [averages, coils, phase encoding, readout].
        Downsampling is applied to the readout dimension.
    decimation
        Decimation factor, by default 100.
        Must be even, since decimation is performed in two steps.
    number_of_stages
        Number of CIC stages.

    Returns
    -------
        Downsampled signal

    Raises
    ------
    ValueError
        Uneven decimation factor.
    """
    cic_samples = 2 * (signal.shape[-1] // decimation)
    cic_decimation = signal.shape[-1] // cic_samples

    # CIC integrator Stages
    for _ in range(number_of_stages):
        signal = np.cumsum(signal, axis=-1)

    # CIC decimation, truncate decimated signal to cic_samples (throw last sample if present)
    decimated_signal = signal[..., :: int(cic_decimation)][..., :cic_samples]

    # Comb Stages
    for _ in range(number_of_stages):
        delayed_signal = np.zeros_like(decimated_signal)
        delayed_signal[..., 1:] = decimated_signal[..., :-1]
        decimated_signal = decimated_signal - delayed_signal

    # Normalization
    gain = np.power(cic_decimation, number_of_stages)
    decimated_signal = decimated_signal / gain

    # Apply FIR decimation with decimation factor of 2 along readout axis
    return decimate(x=decimated_signal, q=2, ftype="fir", axis=-1)
