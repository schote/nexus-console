"""Signal-to-noise ratio (SNR) calculation."""
import numpy as np


def signal_to_noise_ratio(signal: np.ndarray, dwell_time: float, window_width: float | int = 3000) -> float:
    """Calculate the signal to noise ratio in dB.

    Parameters
    ----------
    signal
        Centered spectrum of the acquired signal
    dwell_time
        Dwell-time of the acquired signal
    window_width
        Estimated window width of the signal in Hz

    Returns
    -------
        Signal to noise ratio in dB
    """
    peak = np.max(np.abs(signal[..., :]))
    fft_freq = np.fft.fftshift(np.fft.fftfreq(signal.shape[-1], dwell_time))

    # Define start and end indices of the window
    half_width = int(window_width / 2)
    peak_position = np.argmax(np.abs(signal[..., :]))
    left_window_idx = np.argmin(np.abs(fft_freq + fft_freq[peak_position] + half_width))
    right_window_idx = np.argmin(np.abs(fft_freq + fft_freq[peak_position] - half_width))

    # Extract pure noise from outside the window containing the peak
    noise = np.concatenate((signal[..., :left_window_idx], signal[..., right_window_idx:]))

    # Return snr in dB
    return 20 * np.log10(peak / np.mean(np.abs(noise)))
