"""Plotting methods."""
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from console.interfaces.unrolled_sequence import UnrolledSequence


def plot_unrolled_sequence(
    sequence: UnrolledSequence,
    time_range: tuple[float, float] = (0, -1),
) -> tuple[mpl.figure.Figure, np.ndarray]:
    """Plot unrolled waveforms for replay.

    Parameters
    ----------
    sequence
        The unrolled/calculated sequence to be plotted.
    time_range
        Specify the time range of the plot in seconds.
        If the second value is smaller then the first or -1, the whole sequence is plotted.

    Returns
    -------
        Matplotlib figure and axis
    """
    fig, axis = plt.subplots(5, 1, figsize=(16, 9))
    spcm_freq = 1 / sequence.dwell_time

    if (seq := sequence.seq).size == 0:
        msg = "No unrolled sequence. Execute `unroll_sequence(...)` first"
        raise RuntimeError(msg)

    seq_start = int(time_range[0] * spcm_freq)
    seq_end = int(time_range[1] * spcm_freq) if time_range[1] > time_range[0] else -1
    samples = np.arange(len(seq) // 4, dtype=float)[seq_start:seq_end] * sequence.dwell_time * 1e3

    rf_signal = seq[0::4][seq_start:seq_end]
    gx_signal = seq[1::4][seq_start:seq_end]
    gy_signal = seq[2::4][seq_start:seq_end]
    gz_signal = seq[3::4][seq_start:seq_end]

    # Get digital signals
    adc_gate = gx_signal.astype(np.uint16) >> 15
    unblanking = gz_signal.astype(np.uint16) >> 15

    # Get gradient waveforms
    rf_signal = rf_signal / np.iinfo(np.int16).max
    gx_signal = np.array((np.uint16(gx_signal) << 1).astype(np.int16) / 2**15)
    gy_signal = np.array((np.uint16(gy_signal) << 1).astype(np.int16) / 2**15)
    gz_signal = np.array((np.uint16(gz_signal) << 1).astype(np.int16) / 2**15)

    axis[0].plot(samples, sequence.rf_output_limit * rf_signal)
    axis[1].plot(samples, sequence.gradient_output_limits[0] * gx_signal)
    axis[2].plot(samples, sequence.gradient_output_limits[1] * gy_signal)
    axis[3].plot(samples, sequence.gradient_output_limits[2] * gz_signal)
    axis[4].plot(samples, adc_gate, label="ADC gate")
    axis[4].plot(samples, unblanking, label="RF unblanking")

    axis[0].set_ylabel("RF [mV]")
    axis[1].set_ylabel("Gx [mV]")
    axis[2].set_ylabel("Gy [mV]")
    axis[3].set_ylabel("Gz [mV]")
    axis[4].set_ylabel("Digital")
    axis[4].legend(loc="upper right")

    _ = [ax.grid(axis="x") for ax in axis]

    axis[4].set_xlabel("Time [ms]")

    return fig, axis


def plot_slices(
    img: np.ndarray,
    vmin: float | None = None,
    vmax: float | None = None,
) -> tuple[mpl.figure.Figure, np.ndarray]:
    """Return sliced plot of 3D image data."""
    num_slices = img.shape[0]
    num_cols = int(np.ceil(np.sqrt(num_slices)))
    num_rows = int(np.ceil(num_slices / num_cols))

    fig, ax = plt.subplots(num_rows, num_cols, figsize=(10, 10))
    ax = ax.ravel()

    total_max = np.amax(np.abs(img)) if not vmax else vmax
    total_min = 0 if not vmin else vmin

    for k, x in enumerate(img[:, ...]):
        ax[k].imshow(np.abs(x), vmin=total_min, vmax=total_max, cmap="gray")
        ax[k].axis("off")
    _ = [a.remove() for a in ax[k + 1:]]

    fig.tight_layout(pad=0.05)
    fig.set_facecolor("black")

    return fig, ax
