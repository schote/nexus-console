"""Testing of sequence unrolling function."""
import tempfile
from pathlib import Path
from types import SimpleNamespace

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
    assert rf_waveform.dtype != complex
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


@pytest.mark.parametrize("phase_offset", [0., np.pi / 2, np.pi, 3 * np.pi / 2])
def test_calculate_rf_amplitude_limit(seq_provider: SequenceProvider, phase_offset: float):
    """RF magnitude exceeding the output limit must raise independent of the phase offset."""
    # Sinc pulse: magnitude varies, the peak is not the maximum of the real part for all phase offsets
    block = pp.make_sinc_pulse(flip_angle=np.pi / 2, duration=200e-6, phase_offset=phase_offset)
    # B1 scaling for a peak magnitude equal to the output limit
    b1_limit = seq_provider.rf_out_limit / (np.max(np.abs(block.signal)) * seq_provider.rf_to_mvolt)

    # Ensure that test succeeds below the output limit (90%)
    larmor_frequency = 2.e6
    rf_waveform, _ = seq_provider._calculate_rf(
        block=block, b1_scaling=0.9 * b1_limit, larmor_frequency=larmor_frequency,
    )
    peak = np.max(np.abs(rf_waveform)) / (0.9 * np.iinfo(np.int16).max)
    assert np.cos(np.pi * larmor_frequency * seq_provider.spcm_dwell_time) <= peak <= 1.01

    # Exceeding the output limit (110%)
    with pytest.raises(ValueError):
        _ = seq_provider._calculate_rf(block=block, b1_scaling=1.1 * b1_limit, larmor_frequency=larmor_frequency)


def test_sequence_rx_data(seq_provider: SequenceProvider, acquisition_parameter: AcquisitionParameter):
    """Labels in blocks must be propagated into RxData.labels for each ADC event."""
    n_samples = 1000
    bw = 20e3
    labels = ["SLC", "SEG", "REP", "AVG", "SET", "ECO", "LIN", "PAR", "NAV", "REV", "NOISE", "IMA", "REF"]
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


def _unrolled_channels(seq_provider: SequenceProvider, unrolled_seq: UnrolledSequence) -> tuple[np.ndarray, np.ndarray]:
    """Return the analog waveforms in mV (RF, gradient 1-3) and the digital signals (bit 15 of gradient 1-3)."""
    seq = unrolled_seq.seq.reshape(-1, 4).T
    waveforms = np.vstack([seq[:1], (seq[1:].view(np.uint16) << 1).view(np.int16)]) / np.iinfo(np.int16).max
    output_limits = np.array([seq_provider.rf_out_limit, *seq_provider.gradient_out_limits])
    return waveforms * output_limits[:, None], seq[1:].view(np.uint16) >> 15


def _compare_gradients(seq_provider: SequenceProvider, unrolled_seq: UnrolledSequence,
                       acquisition_parameter: AcquisitionParameter) -> None:
    """Compare the unrolled gradient waveforms to the pypulseq waveforms, considering scaling and channel assignment."""
    analog, _ = _unrolled_channels(seq_provider, unrolled_seq)
    time = np.arange(unrolled_seq.sample_count) * seq_provider.spcm_dwell_time
    channels = acquisition_parameter.channel_assignment.to_list()
    fov_scaling = acquisition_parameter.fov_scaling.to_list()
    for wave, channel, scaling in zip(seq_provider.waveforms(), channels, fov_scaling, strict=True):
        # Gradient waveform in Hz/m to output voltage in mV
        mvolt_per_hz = scaling / (
            seq_provider.system.gamma * 1e-3 * seq_provider.gpa_gain[channel - 1] * seq_provider.grad_eff[channel - 1]
        )
        expected = np.interp(time, wave[0], wave[1], left=0, right=0) * mvolt_per_hz if wave.size else 0 * time
        # Deviation of the linear interpolation on the card raster and the 15 bit resolution of the gradient channels
        tolerance = 0.01 * np.max(np.abs(expected)) + 2 * seq_provider.gradient_out_limits[channel - 1] / 2**15
        np.testing.assert_allclose(analog[channel], expected, rtol=0, atol=tolerance)


def test_unrolled_gradient_waveforms(seq_provider: SequenceProvider, acquisition_parameter: AcquisitionParameter):
    """Unrolled gradients must match the pypulseq waveforms of all gradient types, delays and spanning blocks."""
    acquisition_parameter.fov_scaling.y = 0.8  # Disabled by the fixture
    system = seq_provider.system
    amp = 0.9 * system.max_grad
    ramp = 1e-3
    t_arb = (np.arange(n := round(4 * ramp / system.grad_raster_time)) + 0.5) / n
    t_ext = np.array([0., ramp / 2, 2 * ramp, 3 * ramp, 4 * ramp])
    for delay in [0., ramp]:
        # Trapezoid, triangle and asymmetric trapezoid with different delays
        seq_provider.add_block(
            pp.make_trapezoid("x", amplitude=amp, rise_time=ramp, flat_time=2 * ramp, delay=delay, system=system),
            pp.make_trapezoid("y", amplitude=-amp, rise_time=ramp, flat_time=0., delay=delay / 2, system=system),
            pp.make_trapezoid(
                "z", amplitude=amp / 2, rise_time=ramp, flat_time=ramp, fall_time=2 * ramp, delay=2 * delay,
                system=system,
            ),
        )
        # Arbitrary gradients
        seq_provider.add_block(
            pp.make_arbitrary_grad("x", amp * np.sin(np.pi * t_arb), first=0., last=0., delay=delay, system=system),
            pp.make_arbitrary_grad(
                "y", -amp * np.sin(np.pi * t_arb) ** 2, first=0., last=0., delay=delay / 2, system=system,
            ),
            pp.make_arbitrary_grad(
                "z", amp / 2 * np.sin(2 * np.pi * t_arb), first=0., last=0., delay=2 * delay, system=system,
            ),
        )
        # Extended trapezoids on non-uniform time raster, the first time point defines the delay
        seq_provider.add_block(
            pp.make_extended_trapezoid("x", times=t_ext + delay, amplitudes=amp * np.array([0, 1, .5, .5, 0])),
            pp.make_extended_trapezoid(
                "y", times=t_ext + delay / 2, amplitudes=amp * np.array([0, -1, 0, 1, 0]), convert_to_arbitrary=True,
            ),
            pp.make_extended_trapezoid("z", times=t_ext + 2 * delay, amplitudes=amp * np.array([0, .5, 1, -.5, 0])),
        )
    # Gradients spanning two blocks, non-zero amplitude at the block boundary
    amplitudes = [("x", amp), ("y", -amp), ("z", amp / 2)]
    seq_provider.add_block(*[
        pp.make_extended_trapezoid(c, times=t_ext[:3], amplitudes=np.array([0, a, a])) for c, a in amplitudes
    ])
    seq_provider.add_block(*[
        pp.make_extended_trapezoid(c, times=t_ext[:3], amplitudes=np.array([a, a, 0])) for c, a in amplitudes
    ])
    assert seq_provider.check_timing()[0]

    unrolled_seq = seq_provider.unroll_sequence(acquisition_parameter)
    _compare_gradients(seq_provider, unrolled_seq, acquisition_parameter)
    _, digital = _unrolled_channels(seq_provider, unrolled_seq)
    assert not digital.any()


def test_unrolled_rf_waveforms(seq_provider: SequenceProvider, acquisition_parameter: AcquisitionParameter):
    """Unrolled RF pulses and unblanking must match the pypulseq waveforms, including frequency and phase offsets."""
    system = seq_provider.system
    duration = 200e-6
    amp = 1 / duration  # Peak amplitude of a 2 pi block pulse

    def peak_normalized(rf: SimpleNamespace) -> SimpleNamespace:
        rf.signal *= amp / np.max(np.abs(rf.signal))
        return rf

    # Block pulse with delay equal to and larger than the dead time
    for delay in [system.rf_dead_time, 3 * system.rf_dead_time]:
        seq_provider.add_block(pp.make_block_pulse(2 * np.pi, duration=duration, delay=delay, system=system))
    # Sinc pulse and complex arbitrary pulse with frequency and phase offset
    seq_provider.add_block(peak_normalized(pp.make_sinc_pulse(
        2 * np.pi, duration=duration, delay=system.rf_dead_time, freq_offset=5e3, phase_offset=np.pi / 2,
        system=system,
    )))
    seq_provider.add_block(peak_normalized(pp.make_arbitrary_rf(
        signal=np.exp(1j * np.linspace(-1, 1, round(duration / system.rf_raster_time)) ** 2), flip_angle=2 * np.pi,
        delay=system.rf_dead_time, freq_offset=-3e3, phase_offset=-np.pi / 4, system=system,
    )))
    # RF unblanking is encoded in bit 15 of gradient channel 3, an overlapping gradient must not be affected
    seq_provider.add_block(
        pp.make_block_pulse(2 * np.pi, duration=duration, delay=1e-3, system=system),
        pp.make_trapezoid("z", amplitude=0.9 * system.max_grad, rise_time=1e-3, flat_time=1e-3, system=system),
    )
    assert seq_provider.check_timing()[0]

    unrolled_seq = seq_provider.unroll_sequence(acquisition_parameter)
    analog, digital = _unrolled_channels(seq_provider, unrolled_seq)
    fs = seq_provider.spcm_freq
    dwell_time = seq_provider.spcm_dwell_time
    rf_wave = seq_provider.waveforms(append_RF=True)[3]
    block_start = 0.
    for block_idx in seq_provider.block_events:
        rf = seq_provider.get_block(block_idx).rf
        block = slice(round(block_start * fs), round((block_start + seq_provider.block_durations[block_idx]) * fs))
        # RF waveform within the shape, unblanking starts the dead time before (sample positions relative to the block)
        start = round(rf.delay * fs)
        stop = start + round(rf.shape_dur * fs)
        rf_samples = np.flatnonzero(analog[0, block])
        assert rf_samples[0] >= start
        assert rf_samples[-1] < stop
        unblanking = np.flatnonzero(digital[2, block])
        np.testing.assert_array_equal(unblanking, np.arange(start - round(rf.dead_time * fs), stop))
        start, stop = start + block.start, stop + block.start

        # Envelope including frequency and phase offset from pypulseq, the carrier phase starts with the shape.
        # One RF raster at the edges is excluded, pypulseq defines the shape at the raster centers.
        margin = round(system.rf_raster_time * fs)
        time = np.arange(start + margin, stop - margin) * dwell_time
        t_wave = rf_wave[0].real
        envelope = np.interp(time, t_wave, rf_wave[1].real) + 1j * np.interp(time, t_wave, rf_wave[1].imag)
        carrier = np.exp(2j * np.pi * acquisition_parameter.larmor_frequency * (time - start * dwell_time))
        expected = np.real(envelope * carrier) * acquisition_parameter.b1_scaling * seq_provider.rf_to_mvolt
        # Deviation of the FFT resampling of the envelope
        tolerance = 0.02 * np.max(np.abs(expected))
        np.testing.assert_allclose(analog[0, start + margin:stop - margin], expected, rtol=0, atol=tolerance)
        block_start += seq_provider.block_durations[block_idx]

    _compare_gradients(seq_provider, unrolled_seq, acquisition_parameter)
    assert not digital[:2].any()


def test_unrolled_adc_gate(seq_provider: SequenceProvider, acquisition_parameter: AcquisitionParameter):
    """ADC gate must cover the pypulseq ADC samples, frequency and phase offsets are passed to the receive data."""
    dwell = 1e-5
    adc = pp.make_adc(
        num_samples=100, dwell=dwell, delay=seq_provider.system.adc_dead_time + 5 * dwell, freq_offset=1e3,
        phase_offset=np.pi / 3, system=seq_provider.system,
    )
    seq_provider.add_block(pp.make_delay(1e-4))
    seq_provider.add_block(adc)
    unrolled_seq = seq_provider.unroll_sequence(acquisition_parameter)
    _, digital = _unrolled_channels(seq_provider, unrolled_seq)
    rx_data = unrolled_seq.rx_data[0]

    # ADC sample times are the centers of the dwell intervals, the gate is extended by the discarded samples
    adc_times, _ = seq_provider.adc_times()
    margin = (0.5 + rx_data.num_samples_discard) * dwell
    start = round((adc_times[0] - margin) * seq_provider.spcm_freq)
    stop = round((adc_times[-1] + margin) * seq_provider.spcm_freq)
    np.testing.assert_array_equal(np.flatnonzero(digital[0]), np.arange(start, stop))
    assert stop - start == rx_data.num_samples_raw
    # Phase reference starts with the ADC gate and ends within
    reference = np.flatnonzero(digital[1])
    assert reference[0] == start
    assert reference[-1] < stop
    assert not digital[2].any()
    assert rx_data.freq_offset == adc.freq_offset
    assert rx_data.phase_offset == adc.phase_offset


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
