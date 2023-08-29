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
