"""Testing of sequence unrolling function."""
import tempfile
from pathlib import Path

import numpy as np
import pypulseq as pp
import pytest

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.dimensions import Dimensions
from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.sequences import tse_3d
from console.utilities.sequences.spectrometry import fid


def _compare_sequences(seq1: pp.Sequence, seq2: pp.Sequence) -> None:
    """Compare two pypulseq sequences and ensure equality."""
    assert seq1 is not None
    assert seq2 is not None
    assert seq1.check_timing()[0] == seq2.check_timing()[0]
    assert seq1.duration()[0] == seq2.duration()[0]
    assert seq1.definitions == seq2.definitions
    assert seq1.evaluate_labels() == seq2.evaluate_labels()
    # Compare adc
    t_adc_1, fp_adc_1 = seq1.adc_times()
    t_adc_2, fp_adc_2 = seq2.adc_times()
    np.testing.assert_array_equal(t_adc_1, t_adc_2)
    np.testing.assert_array_equal(fp_adc_1, fp_adc_2)
    # Compare k-space trajectory
    k_traj_adc_1, k_traj_1, t_excitation_1, t_refocusing_1, _ = seq1.calculate_kspace()
    k_traj_adc_2, k_traj_2, t_excitation_2, t_refocusing_2, _ = seq2.calculate_kspace()
    np.testing.assert_array_equal(k_traj_adc_1, k_traj_adc_2)
    np.testing.assert_array_equal(k_traj_1, k_traj_2)
    np.testing.assert_array_equal(t_excitation_1, t_excitation_2)
    np.testing.assert_array_equal(t_refocusing_1, t_refocusing_2)

def test_unrolling(seq_provider: SequenceProvider, test_sequence, acquisition_parameter):
    """Test unrolled sequence plot."""
    assert test_sequence.check_timing()[0]
    seq_provider.from_pypulseq(test_sequence)
    unrolled_seq: UnrolledSequence = seq_provider.unroll_sequence(acquisition_parameter)
    assert unrolled_seq.duration == test_sequence.duration()[0]

def test_sequence_provider_to_pypulseq(seq_provider: SequenceProvider, test_sequence: pp.Sequence) -> None:
    """Test if sequence can be generated from sequence provider."""
    # Ensure test sequence is valid
    assert test_sequence.check_timing()[0]
    seq_provider.from_pypulseq(test_sequence)
    sequence_out = seq_provider.to_pypulseq()
    assert isinstance(sequence_out, pp.Sequence)

    # Test sequence loaded to sequence provider
    _compare_sequences(test_sequence, sequence_out)

    # Save sequences and compare file content
    tmp_dir = Path(tempfile.mkdtemp())
    sliced_file = tmp_dir / "sliced.seq"
    reference_file = tmp_dir / "reference.seq"

    sequence_out.write(sliced_file)
    test_sequence.write(reference_file)
    # Compare file content
    with Path.open(sliced_file, "r") as fh_sliced, Path.open(reference_file, "r") as fh_ref:
        content_sliced = fh_sliced.read()
        content_ref = fh_ref.read()
    assert content_sliced == content_ref

def test_sequence_provider_write_fid_sequence(seq_provider: SequenceProvider, tmp_path: Path) -> None:
    """Test if sequence can be generated from sequence provider."""
    seq = fid.constructor()
    seq_provider.from_pypulseq(seq)

    # Save and reload reference sequence
    reference_file = tmp_path / "reference.seq"
    seq.write(reference_file)
    seq_1 = pp.Sequence()
    seq_1.read(reference_file)

    # Save and reload sequence through sequence provider
    provider_file = tmp_path / "seq_provider.seq"
    seq_provider.write(provider_file)
    seq_2 = pp.Sequence()
    seq_2.read(provider_file)

    # Compare block durations
    for k in range(len(seq.block_events)):
        block_1 = seq_1.get_block(k+1)
        block_2 = seq_2.get_block(k+1)
        assert block_1.block_duration == block_2.block_duration

def test_sequence_provider_to_pypulseq_tse(seq_provider: SequenceProvider) -> None:
    """Ensure TSE sequence remains unchanged when imported to sequence provider."""
    seq, _ = tse_3d.constructor(
        n_enc=Dimensions(16, 32, 32),
        # fov=Dimensions(x=140., y=140., z=140.),
        etl=7,
        echo_time=20.e-3,
        trajectory=tse_3d.Trajectory.INOUT,
        system=seq_provider.system,
    )

    seq_provider.from_pypulseq(seq)
    sequence_out = seq_provider.to_pypulseq()

    _compare_sequences(seq, seq_provider)
    _compare_sequences(seq, sequence_out)


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
    assert d["output_limits"] == seq_provider.gradient_out_limits

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
    """unroll_sequence should fail when incorrect value for channel assignment is set."""
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

    grad = seq_provider._calculate_gradient(
        block=block, fov_scaling=1.0, offset=0.0, output_channel=1,
    )

    # Output is uint16-view of int16 >> 1
    assert isinstance(grad, np.ndarray)
    assert grad.dtype == np.uint16
    assert grad.size == pytest.approx(round(block.shape_dur / seq_provider.spcm_dwell_time))

    # Test exceptions
    with pytest.raises(ValueError):
        _ = seq_provider._calculate_gradient(
            block=block, fov_scaling=1., offset=seq_provider.gradient_out_limits[1], output_channel=1,
        )

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
    grad = seq_provider._calculate_gradient(
        block=block, fov_scaling=1.0, offset=0.0, output_channel=1,
    )

    assert isinstance(grad, np.ndarray)
    assert grad.dtype == np.uint16
    assert grad.size == pytest.approx(round(total_dur / seq_provider.spcm_dwell_time))

    # Test exceptions
    with pytest.raises(ValueError):
        _ = seq_provider._calculate_gradient(
            block=block, fov_scaling=1., offset=seq_provider.gradient_out_limits[1], output_channel=1,
        )

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


def test_sequence_rx_data(seq_provider: SequenceProvider, acquisition_parameter: AcquisitionParameter):
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


@pytest.mark.parametrize("dead_time", [0., 10e-3])
def test_adc_presampling(seq_provider: SequenceProvider, acquisition_parameter: AcquisitionParameter, dead_time: float):
    """Verify that dead_time is used for pre and post samples which are to be discarded after decimation."""
    adc_bw = 20e3
    adc_dwell = 1/adc_bw
    num_samples_discard = round(dead_time/adc_dwell)
    num_samples = 100
    # ADC dead time is a system parameter and should be set in sequence system
    seq_provider.system.adc_dead_time = dead_time
    # Define adc event
    adc = pp.make_adc(
        delay=dead_time,
        num_samples=num_samples,
        dwell=adc_dwell,
        system=seq_provider.system,
    )
    # Unroll sequence
    seq_provider.add_block(adc)
    seq_unrolled = seq_provider.unroll_sequence(acquisition_parameter)
    rx_data = seq_unrolled.rx_data[0]

    assert rx_data.num_samples == num_samples
    assert rx_data.num_samples_discard == num_samples_discard
