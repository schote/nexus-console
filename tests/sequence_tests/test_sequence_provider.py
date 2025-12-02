"""Testing of sequence unrolling function."""
import tempfile
from pathlib import Path

import numpy as np
import pypulseq as pp
import pytest

from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import SequenceProvider


def test_unrolling(seq_provider: SequenceProvider, test_sequence, acquisition_parameter):
    """Test unrolled sequence plot."""
    assert test_sequence.check_timing()[0]

    seq_provider.from_pypulseq(test_sequence)
    unrolled_seq: UnrolledSequence = seq_provider.unroll_sequence(acquisition_parameter)
    assert unrolled_seq.duration == test_sequence.duration()[0]


def test_sequence_provider_to_pypulseq(seq_provider: SequenceProvider, test_sequence):
    """Test if sequence can be generated from sequence provider."""
    seq_provider.from_pypulseq(test_sequence)
    sequence_out = seq_provider.to_pypulseq()

    assert sequence_out is not None

    for key, value in vars(test_sequence).items():
        assert hasattr(sequence_out, key)
        assert getattr(sequence_out, key) == value

    assert sequence_out.duration()[0] == test_sequence.duration()[0]

    # Save sequences and compare file content
    tmp_dir = Path(tempfile.mkdtemp())
    sliced_file = tmp_dir / "sliced.seq"
    reference_file = tmp_dir / "reference.seq"

    sequence_out.write(sliced_file)
    test_sequence.write(reference_file)

    with open(sliced_file, "r") as fh_sliced, open(reference_file, "r") as fh_ref:
        content_sliced = fh_sliced.read()
        content_ref = fh_ref.read()
    assert content_sliced == content_ref


def test_from_pypulseq(seq_provider):
    """from_pypulseq must raise AttributeError when passed an object without .system."""
    with pytest.raises(AttributeError):
        seq_provider.from_pypulseq(object())


def test_dict_contains_basic_config(seq_provider: SequenceProvider):
    """Ensure dict() exposes the main configuration for logging/debugging."""
    d = seq_provider.dict()
    assert set(d.keys()) == {
        "rf_to_mvolt",
        "spcm_freq",
        "spcm_dwell_time",
        "gpa_gain",
        "gradient_efficiency",
        "output_limits",
    }
    # Values agree with constructor
    np.testing.assert_approx_equal(d["spcm_freq"], 1 / seq_provider.spcm_dwell_time)
    assert d["rf_to_mvolt"] == seq_provider.rf_to_mvolt
    assert d["output_limits"] == seq_provider.output_limits


def test_from_pypulseq_system_limit_violation(seq_provider: SequenceProvider, test_sequence):
    """from_pypulseq should raise ValueError when sequence system exceeds device limits."""
    _max_grad = seq_provider.system_limits.max_grad
    seq_provider.system_limits.max_grad = 0.0
    with pytest.raises(ValueError):
        seq_provider.from_pypulseq(test_sequence)
    seq_provider.system_limits.max_grad = _max_grad

    _max_slew = seq_provider.system_limits.max_slew
    seq_provider.system_limits.max_grad = 0.0
    with pytest.raises(ValueError):
        seq_provider.from_pypulseq(test_sequence)
    seq_provider.system_limits.max_slew = _max_slew

    _grad_raster_time = seq_provider.system_limits.grad_raster_time
    seq_provider.system_limits.grad_raster_time = 0.0
    with pytest.raises(ValueError):
        seq_provider.from_pypulseq(test_sequence)
    seq_provider.system_limits.grad_raster_time = _grad_raster_time

    _adc_raster_time = seq_provider.system_limits.adc_raster_time
    seq_provider.system_limits.adc_raster_time = 0.0
    with pytest.raises(ValueError):
        seq_provider.from_pypulseq(test_sequence)
    seq_provider.system_limits.adc_raster_time = _adc_raster_time

    _rf_raster_time = seq_provider.system_limits.rf_raster_time
    seq_provider.system_limits.rf_raster_time = 0.0
    with pytest.raises(ValueError):
        seq_provider.from_pypulseq(test_sequence)
    seq_provider.system_limits.rf_raster_time = _rf_raster_time

    _block_duration_raster = seq_provider.system_limits.block_duration_raster
    seq_provider.system_limits.block_duration_raster = 0.0
    with pytest.raises(ValueError):
        seq_provider.from_pypulseq(test_sequence)
    seq_provider.system_limits.block_duration_raster = _block_duration_raster

    _adc_dead_time = seq_provider.system_limits.adc_dead_time
    seq_provider.system_limits.adc_dead_time = -10.
    with pytest.raises(ValueError):
        seq_provider.from_pypulseq(test_sequence)
    seq_provider.system_limits.adc_dead_time = _adc_dead_time

    _rf_dead_time = seq_provider.system_limits.rf_dead_time
    seq_provider.system_limits.rf_dead_time = -10.
    with pytest.raises(ValueError):
        seq_provider.from_pypulseq(test_sequence)
    seq_provider.system_limits.rf_dead_time = _rf_dead_time

    _rf_ringdown_time = seq_provider.system_limits.rf_ringdown_time
    seq_provider.system_limits.rf_ringdown_time = -10.
    with pytest.raises(ValueError):
        seq_provider.from_pypulseq(test_sequence)
    seq_provider.system_limits.rf_ringdown_time = _rf_ringdown_time


def test_invalid_larmor_frequency(
    seq_provider: SequenceProvider,
    test_sequence,
    acquisition_parameter,
):
    """unroll_sequence should fail when Larmor frequency violates Nyquist limit."""
    seq_provider.from_pypulseq(test_sequence)
    # Set invalid larmor frequencies
    acquisition_parameter.larmor_frequency = seq_provider.spcm_freq / 2
    with pytest.raises(ValueError):
        seq_provider.unroll_sequence(acquisition_parameter)
    acquisition_parameter.larmor_frequency = 0.
    with pytest.raises(ValueError):
        seq_provider.unroll_sequence(acquisition_parameter)

def test_invalid_channel_assignment(
    seq_provider: SequenceProvider,
    test_sequence,
    acquisition_parameter,
):
    """unroll_sequence should fail when Larmor frequency violates Nyquist limit."""
    seq_provider.from_pypulseq(test_sequence)
    # Set invalid values
    acquisition_parameter.channel_assignment.x = 4
    with pytest.raises(ValueError):
        seq_provider.unroll_sequence(acquisition_parameter)


def test_calculate_arbitrary_gradient_block(seq_provider: SequenceProvider):
    """Cover _calculate_gradient for type 'grad'."""
    block = pp.make_arbitrary_grad(
        channel="x",
        waveform=np.array([0.0, 0.5, 0.9], dtype=float),
    )

    grad = seq_provider._calculate_gradient(block=block, fov_scaling=1.0, offset=0.0)

    # Output is uint16-view of int16 >> 1
    assert isinstance(grad, np.ndarray)
    assert grad.dtype == np.uint16
    assert grad.size == pytest.approx(round(block.shape_dur / seq_provider.spcm_dwell_time))

    # Test exceptions
    with pytest.raises(ValueError):
        _ = seq_provider._calculate_gradient(block=block, fov_scaling=1., offset=seq_provider.output_limits[1])
    block.channel = "a"
    with pytest.raises(ValueError):
        _ = seq_provider._calculate_gradient(block=block, fov_scaling=1., offset=0.)


def test_calculate_trapezoid_gradient_block(seq_provider: SequenceProvider):
    """Cover _calculate_gradient for type 'trap'."""
    block = pp.make_trapezoid(
        channel="y",
        amplitude=0.5,
        rise_time=100e-6,
        flat_time=200e-6,
        fall_time=100e-6,
    )

    total_dur = block.rise_time + block.flat_time + block.fall_time
    grad = seq_provider._calculate_gradient(block=block, fov_scaling=1.0, offset=0.0)

    assert isinstance(grad, np.ndarray)
    assert grad.dtype == np.uint16
    assert grad.size == pytest.approx(round(total_dur / seq_provider.spcm_dwell_time))

    # Test exceptions
    with pytest.raises(ValueError):
        _ = seq_provider._calculate_gradient(block=block, fov_scaling=1., offset=seq_provider.output_limits[1])
    block.channel = "a"
    with pytest.raises(ValueError):
        _ = seq_provider._calculate_gradient(block=block, fov_scaling=1., offset=0.)

def test_calculate_rf_block(seq_provider: SequenceProvider):
    """Cover _calculate_rf for valid and invalid RF blocks."""
    block = pp.make_block_pulse(flip_angle=np.pi, duration=100e-6)
    rf_waveform, rf_unblanking = seq_provider._calculate_rf(block=block, b1_scaling=1.0, larmor_frequency=2.e6)

    # Basic checks
    assert isinstance(rf_waveform, np.ndarray)
    assert isinstance(rf_unblanking, np.ndarray)
    assert rf_waveform.dtype == complex
    assert rf_unblanking.dtype == np.uint16

    # Number of computed RF samples must follow logic:
    num_samples = round(block.shape_dur * seq_provider.spcm_freq)
    assert rf_waveform.size == num_samples
    assert rf_unblanking.size == num_samples

    # Unblanking must have high bit from start (no delay or ring down here)
    assert np.all(rf_unblanking[:] == 2**15)

    # Check dead time
    block.dead_time = 20e-6
    dead_time_samples = round(block.dead_time * seq_provider.spcm_freq)
    rf_waveform, rf_unblanking = seq_provider._calculate_rf(block=block, b1_scaling=1.0, larmor_frequency=2.e6)
    assert rf_waveform.size == num_samples + dead_time_samples
    assert rf_unblanking.size == num_samples + dead_time_samples

    # Check delay (note only max(delay, dead_time) is added)
    block.delay = 100e-6
    delay_samples = round(block.delay * seq_provider.spcm_freq)
    rf_waveform, rf_unblanking = seq_provider._calculate_rf(block=block, b1_scaling=1.0, larmor_frequency=2.e6)
    assert rf_waveform.size == num_samples + delay_samples
    assert rf_unblanking.size == num_samples + delay_samples

    # Check exception with invalid scaling (110%)
    invalid_scaling = 1.1 * np.iinfo(np.int16).max / np.amax(rf_waveform)
    with pytest.raises(ValueError):
        _ = seq_provider._calculate_rf(block, b1_scaling=invalid_scaling, larmor_frequency=2.e6)
    # Check exception with invalid Larmor frequency (<0)
    with pytest.raises(ValueError):
        _ = seq_provider._calculate_rf(block, b1_scaling=invalid_scaling, larmor_frequency=-1.e3)


def test_get_rf_events(seq_provider, test_sequence):
    """get_rf_events should expose RF events from the RF library."""
    seq_provider.from_pypulseq(test_sequence)

    rf_events = seq_provider.get_rf_events()
    assert len(rf_events) >= 1

    rf_id, rf_block = rf_events[0]
    assert isinstance(rf_id, int)
    # rf_block should be something pypulseq-like (namespace or RF block)
    assert hasattr(rf_block, "type")
    assert rf_block.type == "rf"


def test_sequence_rx_data(seq_provider: SequenceProvider, acquisition_parameter):
    """Labels in blocks must be propagated into RxData.labels for each ADC event."""
    n_samples = 1000
    bw = 20e3
    labels = ['SLC', 'SEG', 'REP', 'AVG', 'SET', 'ECO', 'LIN', 'PAR', 'NAV', 'REV', 'NOISE', 'IMA', 'REF']
    for k, label in enumerate(labels):
        seq_provider.add_block(pp.make_delay(1e-6), pp.make_label(label, "SET", k))
    seq_provider.add_block(pp.make_adc(num_samples=n_samples, dwell=1/bw))

    unrolled = seq_provider.unroll_sequence(acquisition_parameter)
    assert len(unrolled.rx_data) >= 1
    rx0: RxData = unrolled.rx_data[0]

    assert rx0.labels is not None

    for k, label in enumerate(labels):
        assert label in rx0.labels
        assert k == rx0.labels[label]

    assert rx0.num_samples == n_samples
    assert rx0.num_samples_raw == n_samples / (bw*seq_provider.spcm_dwell_time)
    assert rx0.dwell_time == 1/bw
