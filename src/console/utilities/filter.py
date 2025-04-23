"""Filter function for processing."""
import numpy as np


def filter_function(nb_points: int):
    """Return a frequency filter for processing.

    Returns a filter function to be applied in the frequency domain.
    It preserves the central frequency (0 Hz) and gradually attenuates higher frequencies
    symmetrically. The filter is designed for use on demodulated data (centered at 0 Hz).
    This function returns a list of filter values to be directly multiplied with your data.

    The filter shape was obtained by curve fitting the frequency response
    of the Pure Devices Drive L MRI Control Unit.

    Parameters
    ----------
    nb_points
        Length of the filter list to be returned.

    Returns
    -------
        List containing the filter data.
    """
    x = np.linspace(-1, 1, nb_points)
    return 0.999 - 1.62 * (x**2) + 1.1 * (x**4) - 0.309 * (x**6)
