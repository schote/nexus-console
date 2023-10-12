"""Plot function for spcm formatted data array."""

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence


def plot_spcm_data(
    sequence: UnrolledSequence, seq_range: tuple[int, int] = (0, -1), use_time: bool = True
) -> tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]:
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

    seq_start = int(seq_range[0])
    seq_end = int(seq_range[1])
    samples = np.arange(sequence.sample_count, dtype=float)[seq_start:seq_end]

    if use_time:
        # Convert sample points to time axis in ms
        samples = samples * sequence.dwell_time * 1e3

    sqncs = np.concatenate(sequence.seq)

    # TODO: Display % of output level

    rf_signal = sqncs[0::num_channels][seq_start:seq_end]
    gx_signal = sqncs[1::num_channels][seq_start:seq_end]
    gy_signal = sqncs[2::num_channels][seq_start:seq_end]
    gz_signal = sqncs[3::num_channels][seq_start:seq_end]

    if not sqncs.dtype == np.int16:
        raise ValueError("Require int16 values to decode digital signal...")

    adc = -(gx_signal >> 15)
    unblanking = -(gy_signal >> 15)

    gx_signal = gx_signal << 1
    gy_signal = gy_signal << 1
    gz_signal = gz_signal << 1

    # else:
    #     adc = np.concatenate(sequence.adc_gate)[seq_range[0]:seq_range[1]]
    #     unblanking = np.concatenate(sequence.rf_unblanking)[seq_range[0]:seq_range[1]]

    axis[0].plot(samples, rf_signal)
    axis[1].plot(samples, gx_signal)
    axis[2].plot(samples, gy_signal)
    axis[3].plot(samples, gz_signal)
    axis[4].plot(samples, adc, label="ADC gate")
    axis[4].plot(samples, unblanking, label="RF unblanking")

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
