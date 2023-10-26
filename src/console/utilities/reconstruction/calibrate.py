"""Calibration methods."""
import numpy as np
from scipy.optimize import curve_fit


def fa_model(samples: np.ndarray, amp: float, amp_offset: float, step_size: float, phase_offset: float) -> np.ndarray:
    """Calculate flip angle model.

    Parameters
    ----------
    samples
        Evaluation points
    amplitude
        Amplitude
    step_size
        Step size
    phase_offset
        Phase offset value in rad

    Returns
    -------
        Returns model applied on evaluation points.
        |amplitude * sin(step_size * x)|
    """
    return np.abs(amp * np.sin(step_size * samples + phase_offset) + amp_offset)


def flip_angle_fit(data: np.ndarray, flip_angles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit flip angle to calibrate transmit power.

    Parameters
    ----------
    x
        Acquisition raw data with 4 dimensions.
        Phase encoding dimension contains the repeated acquisitions with different TX power.
    flip_angles
        Flip angles that correspond to phase encoding dimension

    Returns
    -------
        Fitted result and amplitude maxima per shot

    Raises
    ------
    ValueError
        Invalid input shapes
    """
    if not len(data.shape) == 4:
        raise ValueError("Invalid input data shape")
    if data.shape[-2] != flip_angles.size:
        raise ValueError("Number of flip angles does not match the number of phase encodings")

    # Calculate averages and take first coil (channel 0)
    data = np.mean(data, axis=0)[0, ...]

    data = np.abs(np.fft.fftshift(np.fft.fft(data, norm="ortho")))

    # Truncate spectrum center to 100 pixels:
    n_samples = 100
    window_start = int(data.shape[-1] / 2 - n_samples / 2)
    data = data[..., window_start : window_start + n_samples]
    amplitudes = np.max(data, axis=-1)

    init = [np.max(amplitudes), np.min(amplitudes), 1, 0]

    # Fit parameters
    # TODO: 2nd parameter contains varianze -> evaluate if fit was successful
    result = curve_fit(fa_model, flip_angles, amplitudes, init, method="lm")
    params = result[0]

    fa_fit = np.arange(flip_angles[0], flip_angles[-1] + 0.1, 0.1)
    amp_fit = fa_model(fa_fit, *params)

    return np.stack([fa_fit, amp_fit], axis=0), amplitudes
