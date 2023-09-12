"""Plot function for spcm formatted data array."""

import matplotlib.pyplot as plt
import numpy as np

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence


def plot_spcm_data(sequence: UnrolledSequence):
    """Plot replay data for spectrum-instrumentation data in final card format.

    Parameters
    ----------
    sequence
        Instance of `UnrolledSequence` object containing the replay data and digital signals.

    Returns
    -------
        Matplotlib figure

    Raises
    ------
    ValueError
        Provided replay data is not in int16 format
    """
    num_channels = 4
    fig, axis = plt.subplots(num_channels + 1, 1, figsize=(16, 9))
    
    sqncs = np.concatenate(sequence.seq)
    
    rf = sqncs[0::num_channels]
    gx = sqncs[1::num_channels]
    gy = sqncs[2::num_channels]
    gz = sqncs[3::num_channels]

    if sequence.is_int16:
        if not sequence.seq.dtype == np.int16:
            raise ValueError("Require int16 values to decode digital signal...")
        
        adc = -1 * (gx >> 15)
        unblanking = -1 * (gy >> 15) 
        
        gx = gx << 1
        gy = gy << 1
        gz = gz << 1

    else:
        adc = np.concatenate(sequence.adc_gate)
        unblanking = np.concatenate(sequence.rf_unblanking)


    axis[0].plot(rf)
    axis[1].plot(gx)
    axis[2].plot(gy)
    axis[3].plot(gz)
    axis[4].plot(adc)
    axis[4].plot(unblanking)
    
    axis[0].set_ylabel("RF")
    axis[1].set_ylabel("Gx")
    axis[2].set_ylabel("Gy")
    axis[3].set_ylabel("Gz")
    axis[4].set_ylabel("Digital")
    axis[4].set_xlabel("Number of samples")

    return fig, axis
