"""Plot function for spcm formatted data array."""

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence


def plot_spcm_data(
    sequence: UnrolledSequence, 
    seq_range: tuple[int, int] = (0, -1), 
    use_time: bool = True) -> (matplotlib.figure.Figure, matplotlib.axes.Axes):
    """Plot replay data for spectrum-instrumentation data in final card format.

    Parameters
    ----------
    sequence
        Instance of `UnrolledSequence` object containing the replay data and digital signals.
    
    seq_range, default = (0, -1)
        Specify the (time/sample point) range of the plot in number of samples. 
        If the second element equals -1, the (time) course is plotted until the end.
        
    use_time, default = False
        Boolean flag which indicates if x-axis is plotted in time [ms] (True) or number of samples (False).

    Returns
    -------
        Matplotlib figure and axis

    Raises
    ------
    ValueError
        Flag in `UnrolledSequence` instance indicates that replay data is in int16, but the actual data type differs.
    """
    num_channels = 4
    fig, axis = plt.subplots(num_channels + 1, 1, figsize=(16, 9))
    
    seq_range = [int(x) for x in seq_range]
    x = np.arange(sequence.sample_count)[seq_range[0]:seq_range[1]]
    
    if use_time:
        # Convert sample points to time axis in ms
        x = x * sequence.dwell_time * 1e3
    
    sqncs = np.concatenate(sequence.seq)
    
    rf = sqncs[0::num_channels][seq_range[0]:seq_range[1]]
    gx = sqncs[1::num_channels][seq_range[0]:seq_range[1]]
    gy = sqncs[2::num_channels][seq_range[0]:seq_range[1]]
    gz = sqncs[3::num_channels][seq_range[0]:seq_range[1]]


    if not sqncs.dtype == np.int16:
        raise ValueError("Require int16 values to decode digital signal...")
    
    adc = -(gx >> 15)
    unblanking = -(gy >> 15) 
    
    gx = gx << 1
    gy = gy << 1
    gz = gz << 1

    # else:
    #     adc = np.concatenate(sequence.adc_gate)[seq_range[0]:seq_range[1]]
    #     unblanking = np.concatenate(sequence.rf_unblanking)[seq_range[0]:seq_range[1]]


    axis[0].plot(x, rf)
    axis[1].plot(x, gx)
    axis[2].plot(x, gy)
    axis[3].plot(x, gz)
    axis[4].plot(x, adc, label="ADC gate")
    axis[4].plot(x, unblanking, label="RF unblanking")
    
    axis[0].set_ylabel("RF")
    axis[1].set_ylabel("Gx")
    axis[2].set_ylabel("Gy")
    axis[3].set_ylabel("Gz")
    axis[4].set_ylabel("Digital")
    axis[4].legend(loc="upper right")
    
    _ = [ax.grid(axis="x") for ax in axis]
    
    if use_time:
        axis[4].set_xlabel("Time [ms]")
    else:
        axis[4].set_xlabel(f"Sample points ({(1/sequence.dwell_time)*1e-6} MHz sample rate)")
    

    return fig, axis
