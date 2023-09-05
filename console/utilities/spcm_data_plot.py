"""Plot function for spcm formatted data array."""

import matplotlib.pyplot as plt
import numpy as np


def plot_spcm_data(data: np.ndarray, contains_gate: bool = False):
    """Plot replay data for spectrum-instrumentation data in final card format.

    Parameters
    ----------
    data
        Numpy array containing the replay data
    contains_gate, optional
        Flag which indicates if replay data is contained in channels 1, 2 and 3, by default False

    Returns
    -------
        Matplotlib figure

    Raises
    ------
    ValueError
        Provided replay data is not in int16 format
    """
    num_channels = 4
    fig, axis = plt.subplots(num_channels + int(contains_gate), 1, figsize=(16, 9))
    minmax = []

    for k in range(num_channels):
        if contains_gate and k > 0:
            if not data[k::num_channels].dtype == np.int16:
                raise ValueError("Require int16 values to decode digital signal...")
            _data = data[k::num_channels] << 1
            _adc = -1 * (data[k::num_channels] >> 15)

            axis[-1].plot(_adc)
            axis[-1].set_ylabel("Digital")

        else:
            _data = data[k::num_channels]

        # Extract min-max values per channel
        _min = _data.min()
        _max = _data.max()
        # Add +-10% of absolute to the calculated limits
        minmax.append((_min - abs(_min) * 0.1, _max + abs(_max) * 0.1))

        axis[k].plot(_data)
        axis[k].set_ylabel(f"Channel {k+1}")

        if not minmax[k][0] == minmax[k][1]:
            axis[k].set_ylim(minmax[k])

    axis[k].set_xlabel("Number of samples")

    return fig
