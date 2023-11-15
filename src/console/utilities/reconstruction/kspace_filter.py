"""Collection of k-space filtering techniques."""
import numpy as np


def gaussian_filter(raw_data: np.ndrray, p1_param: float = 1 / 2, p2_param: float = 1 / 6) -> np.ndarray:
    """Apply gassian filter on k-space data.

    Parameters
    ----------
    raw_data
        k-space data
    p1_param, optional
        filter parameter 1, by default 1/2
    p2_param, optional
        filter parameter 2, by default 1/6

    Returns
    -------
        Filtered raw data (kspace)
    """
    input_shape = np.shape(raw_data)
    filter_mat = 1
    for dim_size in input_shape:
        p1 = dim_size * p1_param
        p2 = dim_size * p2_param
        filter_vec = np.exp(-(np.square(np.arange(dim_size) - p1) / (p2**2)))
        filter_mat = np.multiply.outer(filter_mat, filter_vec)
    return np.multiply(raw_data, filter_mat)


def sine_bell_squared_filter(raw_data: np.ndarray, filter_strength: float = 1.0) -> np.ndarray:
    """Apply sine bell squared filter.

    Parameters
    ----------
    raw_data
        k-space data
    filter_strength, optional
        Strength of filter kernel, by default 1

    Returns
    -------
        Filtered raw data (k-space)
    """
    input_shape = np.shape(raw_data)
    filter_mat = 1
    for dim_size in input_shape:
        p1 = dim_size / 2
        axis = np.linspace(-dim_size / 2, dim_size / 2, dim_size)
        filter_vec = 1 - filter_strength * np.square(np.cos(0.5 * np.pi * (axis - p1) / (dim_size - p1)))
        filter_mat = np.multiply.outer(filter_mat, filter_vec)
    return np.multiply(raw_data, filter_mat)
