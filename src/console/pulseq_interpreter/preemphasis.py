"""Gradient pre-emphasis of the unrolled replay buffer."""
import numpy as np
from scipy.signal import lfilter

from console.interfaces.device_configuration import ChannelPreemphasis, GradientPreemphasis

INT16_MAX = np.iinfo(np.int16).max


def preemphasize(gradient: np.ndarray, channel: ChannelPreemphasis, dwell_time: float) -> np.ndarray:
    """Return the pre-emphasized waveform of one gradient channel.

    Each term adds ``amplitude * e``, the waveform derivative filtered by ``exp(-t/time_constant)``:
    ``e[k] = p * e[k-1] + g[k] - g[k-1]`` with ``p = exp(-dwell_time/time_constant)``.
    The terms are applied in parallel, which stays numerically stable for p close to 1.
    """
    g = gradient.astype(np.float64)
    u = g.copy()
    for term in channel.terms:
        p = np.exp(-dwell_time / term.time_constant)
        u += term.amplitude * lfilter([1., -1.], [1., -p], g)

    # Advance the output to compensate the delay of the gradient chain
    shift = round(channel.delay / dwell_time)
    if shift > 0:
        u = np.concatenate((u[shift:], np.zeros(shift)))
    return u


def apply_gradient_preemphasis(seq: np.ndarray, config: GradientPreemphasis, dwell_time: float) -> None:
    """Apply the pre-emphasis in place to the gradient channels of an interleaved replay buffer.

    Gradients are stored in bits 0-14 of channels 1-3, bit 15 (digital signal) is preserved.

    Raises
    ------
    ValueError
        A pre-emphasized waveform exceeds the output range of its channel.
    """
    for channel, settings in config.channels.items():
        raw = seq[channel::4].view(np.uint16)
        digital = raw & 0x8000
        gradient = (raw << 1).view(np.int16)

        u = preemphasize(gradient, settings, dwell_time)
        if (peak := np.abs(u).max()) > INT16_MAX:
            excess = (peak / INT16_MAX - 1) * 100
            msg = f"Pre-emphasized gradient of channel {channel} exceeds output limit by {excess:.1f}%."
            raise ValueError(msg)

        seq[channel::4] = (u.astype(np.int16).view(np.uint16) >> 1) | digital
