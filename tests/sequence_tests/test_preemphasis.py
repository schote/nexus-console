"""Tests of the gradient pre-emphasis."""
from pathlib import Path

import numpy as np
import pypulseq as pp
import pytest
from scipy.signal import lfilter

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.device_configuration import ChannelPreemphasis, GradientPreemphasis, PreemphasisTerm
from console.pulseq_interpreter.preemphasis import apply_gradient_preemphasis, preemphasize
from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.load_configuration import load_system_limits

DWELL_TIME = 5e-8  # 20 MHz transmit card
# Unrolled gradients are truncated to int16 (< 1) and stored with 15 bit (LSB dropped, < 1)
QUANTIZATION_ERROR = 2

system = load_system_limits(Path("examples/example_device_config.yaml")).get_opts()


def _gradient(seq: np.ndarray, channel: int) -> np.ndarray:
    """Return the int16 gradient of a channel from an interleaved replay buffer."""
    return (seq[channel::4].view(np.uint16) << 1).view(np.int16)


def _buffer_with_gradient(gradient: np.ndarray, channel: int) -> np.ndarray:
    """Return an interleaved replay buffer containing the gradient on the given channel."""
    seq = np.zeros(4 * gradient.size, dtype=np.int16)
    seq[channel::4] = gradient.astype(np.int16).view(np.uint16) >> 1
    return seq


def _single_term(amplitude: float, time_constant: float, delay: float = 0.) -> ChannelPreemphasis:
    return ChannelPreemphasis(delay=delay, terms=[PreemphasisTerm(amplitude=amplitude, time_constant=time_constant)])


@pytest.fixture()
def provider() -> SequenceProvider:
    """Sequence provider with a gradient scaling that uses most of the int16 range at max_grad."""
    return SequenceProvider(
        gradient_efficiency=(4e-3, 4e-3, 4e-3),
        gpa_gain=(1.0, 1.0, 1.0),
        gradient_output_limits=(6000, 6000, 6000),
        gradients_50ohms=False,
        rf_output_limit=200,
        rf_50ohms=True,
        rf_to_mvolt=5e-3,
        spcm_dwell_time=DWELL_TIME,
        system=system,
    )


def test_preemphasis_inverts_eddy_currents() -> None:
    """Pre-emphasis followed by the eddy-current model reproduces the nominal waveform."""
    # Single-exponential eddy-current model on the frame raster:
    # g_real = u - alpha * (du/dt * exp(-t/tau)), i.e. H(z) = 1 - alpha (1 - z^-1) / (1 - q z^-1)
    alpha, tau = 0.05, 20e-6
    q = np.exp(-DWELL_TIME / tau)
    # Exact discrete inverse 1/H(z): amplitude alpha/(1-alpha), pole (q-alpha)/(1-alpha)
    pole = (q - alpha) / (1 - alpha)
    channel = _single_term(amplitude=alpha / (1 - alpha), time_constant=-DWELL_TIME / np.log(pole))

    amplitude = 10000.
    nominal = np.zeros(4000)
    nominal[500:2500] = amplitude

    u = preemphasize(nominal, channel, DWELL_TIME)
    real = u - alpha * lfilter([1., -1.], [1., -q], u)

    # The corrected output equals the nominal step up to float64 round-off of the recursions
    np.testing.assert_allclose(real, nominal, rtol=0, atol=1e-9 * amplitude)


def test_preemphasis_tail_crosses_block_boundary(
    provider: SequenceProvider, acquisition_parameter: AcquisitionParameter
) -> None:
    """The compensation of a gradient decays into the following block without gradient event."""
    trap = pp.make_trapezoid(channel="x", amplitude=0.5 * system.max_grad, flat_time=1e-3, system=system)
    delay = pp.make_delay(1e-3)
    seq = pp.Sequence(system=system)
    seq.add_block(trap)
    seq.add_block(delay)
    provider.from_pypulseq(seq)

    acquisition_parameter.fov_scaling.x = 1.
    channel = acquisition_parameter.channel_assignment.x
    trap_end = round(pp.calc_duration(trap) / DWELL_TIME)
    delay_frames = round(delay.delay / DWELL_TIME)

    nominal = _gradient(provider.unroll_sequence(acquisition_parameter).seq, channel)

    beta, tau = 0.1, 200e-6
    provider.gradient_preemphasis = GradientPreemphasis(channels={channel: _single_term(beta, tau)})
    corrected = _gradient(provider.unroll_sequence(acquisition_parameter).seq, channel)

    # Nominal waveform is zero in the delay block, the corrected one starts with the analytical tail
    # beta * e(t_end): a linear ramp of height A and duration T gives e = A * tau/T * (1 - exp(-T/tau)),
    # the rising ramp contribution decays during flat top and falling ramp.
    # Tolerance: quantization plus discretization of the continuous ramp model (beta * A * dwell/tau < 1)
    amplitude = float(nominal.max())

    def ramp(duration: float) -> float:
        return amplitude * tau / duration * (1 - np.exp(-duration / tau))

    e_end = ramp(trap.rise_time) * np.exp(-(trap.flat_time + trap.fall_time) / tau) - ramp(trap.fall_time)
    tail = corrected[trap_end:trap_end + delay_frames].astype(np.float64)
    assert not nominal[trap_end:trap_end + delay_frames].any()
    assert tail[0] == pytest.approx(beta * e_end, abs=QUANTIZATION_ERROR + 1)

    # Without gradient change, the tail decays exactly as exp(-t/tau) across the block boundary
    expected = tail[0] * np.exp(-np.arange(delay_frames) * DWELL_TIME / tau)
    np.testing.assert_allclose(tail, expected, rtol=0, atol=QUANTIZATION_ERROR)


def test_preemphasis_preserves_digital_signals(
    seq_provider: SequenceProvider,
    test_sequence: pp.Sequence,
    acquisition_parameter: AcquisitionParameter,
) -> None:
    """Pre-emphasis changes neither the RF channel nor the digital signals in bit 15."""
    seq_provider.from_pypulseq(test_sequence)
    reference = seq_provider.unroll_sequence(acquisition_parameter).seq

    channel = ChannelPreemphasis(
        delay=2e-6,
        terms=[
            PreemphasisTerm(amplitude=0.05, time_constant=50e-6),
            PreemphasisTerm(amplitude=0.02, time_constant=1e-3),
        ],
    )
    seq_provider.gradient_preemphasis = GradientPreemphasis(channels={1: channel, 2: channel, 3: channel})
    corrected = seq_provider.unroll_sequence(acquisition_parameter).seq

    # RF samples and ADC gate, phase reference and unblanking bits are untouched
    np.testing.assert_array_equal(corrected[0::4], reference[0::4])
    for ch in (1, 2, 3):
        np.testing.assert_array_equal(corrected[ch::4].view(np.uint16) >> 15, reference[ch::4].view(np.uint16) >> 15)


def test_preemphasis_delay_advances_channel() -> None:
    """The delay advances the whole channel by round(delay / dwell_time) frames and pads with zeros."""
    delay = 2e-6
    shift = round(delay / DWELL_TIME)
    nominal = np.zeros(1000)
    nominal[200:600] = 1000.

    u = preemphasize(nominal, ChannelPreemphasis(delay=delay), DWELL_TIME)

    # Pure time shift without compensation terms
    np.testing.assert_array_equal(u[:-shift], nominal[shift:])
    np.testing.assert_array_equal(u[-shift:], 0.)


def test_preemphasis_exceeding_output_limit_raises() -> None:
    """A pre-emphasized waveform above the int16 output range raises an error."""
    amplitude, beta = 30000, 0.2  # overshoot amplitude * (1 + beta) > 32767
    gradient = np.zeros(2000)
    gradient[500:] = amplitude
    seq = _buffer_with_gradient(gradient, channel=1)
    config = GradientPreemphasis(channels={1: _single_term(beta, 100e-6)})

    with pytest.raises(ValueError, match="exceeds output limit"):
        apply_gradient_preemphasis(seq, config, DWELL_TIME)
