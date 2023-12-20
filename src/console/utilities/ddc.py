"""Digital down converter (DDC) function."""
import numpy as np
from scipy.signal import decimate


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
    DeprecationWarning("This method is deprecated.")
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


def filter_moving_average(signal, decimation: int = 100, overlap: int = 4):
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
    kernel_noise = np.random.choice(list(range(-9, 0)) + list(range(1, 10)), kernel_size) * 1e-12
    kernel_space = np.linspace(-1, 1, kernel_size) + kernel_noise
    # Define kernel
    kernel = np.exp(-1 / (1 - kernel_space**2)) * np.sin(kernel_space * 2.073 * np.pi) / kernel_space
    # Integral for normalization
    norm = np.sum(kernel)

    # Calculate size of down-sampled signal
    num_ddc_samples = signal.shape[-1] // decimation
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
    if not (cic_decimation := decimation / 2).is_integer():
        raise ValueError("Decimation factor must be even.")

    # Integrator Stages
    for _ in range(number_of_stages):
        signal = np.cumsum(signal)

    # Decimation
    decimated_signal = signal[:: int(cic_decimation)]

    # Comb Stages
    for _ in range(number_of_stages):
        delayed_signal = np.zeros_like(decimated_signal)
        delayed_signal[1:] = decimated_signal[:-1]
        decimated_signal = decimated_signal - delayed_signal

    # Normalization
    gain = np.power(cic_decimation, number_of_stages)
    decimated_signal = decimated_signal / gain

    return decimate(x=decimated_signal, q=2, ftype="fir")
