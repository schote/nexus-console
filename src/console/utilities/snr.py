import numpy as np


def signal_to_noise_ratio(signal: np.ndarray, noise_threshold: float = 0.2, use_rms: bool = False) -> float:
    """Calculate the signal to noise ratio.

    Parameters
    ----------
    signal
        Signal to be evaluated
    noise_threshold, optional
        Threshold for noise level, by default 0.2
    use_rms, optional
        Flag to switch between RMS and mean abs. of the noise to calculate noise level, by default False

    Returns
    -------
        SNR value
    """
    # Calculte signal by thresholding
    signal_win = signal[np.abs(signal) > noise_threshold * np.max(np.abs(signal))]
    noise_win = signal[np.abs(signal) <= noise_threshold * np.max(np.abs(signal))]

    if use_rms:
        noise = np.sqrt(np.mean(noise_win**2))
    else:
        noise = np.mean(np.abs(noise_win))  # Mean abs

    return np.abs(np.max(signal_win) / noise)
