"""Test configuration file."""

import tempfile
from collections.abc import Callable, Generator
from pathlib import Path

import numpy as np
import pypulseq as pp
import pytest

from console.interfaces.acquisition_parameter import AcquisitionParameter, Dimensions
from console.interfaces.rx_data import RxData
from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.load_configuration import load_system_limits

system = load_system_limits(Path("examples/example_device_config.yaml")).get_opts()


@pytest.fixture()
def seq_provider() -> SequenceProvider:
    """Construct default sequence provider as fixture for testing."""
    return SequenceProvider(
        gradient_efficiency=(0.4, 0.4, 0.4),
        gpa_gain=(1.0, 1.0, 1.0),
        gradient_output_limits=(6000, 6000, 6000),
        gradients_50ohms=False,
        rf_output_limit=200,
        rf_50ohms=True,
        rf_to_mvolt=5e-3,
        spcm_dwell_time=5e-8,
        system=system,
    )


@pytest.fixture()
def random_complex_data() -> Callable:
    """Return random complex valued numpy array with given shape."""
    rng = np.random.default_rng(seed=0)

    def _factory(shape: tuple) -> np.ndarray:
        re = rng.random(size=shape)
        im = rng.random(size=shape)
        return re + 1j * im
    return _factory


@pytest.fixture()
def random_acquisition_data() -> Callable:
    """Construct random acquisition data using factory function.

    Arguments:
        num_coils: int
        num_samples: int
        num_acquisitions: int
        num_averages: int

    Returns
    -------
        Random acquisition data array with dimensions: [averages, coils, phase encoding, readout]
    """
    rng = np.random.default_rng(seed=0)

    def _factory(num_samples: int, num_acquisitions: int, num_averages: int = 1, num_coils: int = 1) -> list[RxData]:
        num_raw_samples = num_samples * 1000
        rx_data = []
        for k_average in range(num_averages):
            for k_acquisition in range(num_acquisitions):
                processed_re = rng.random(size=(num_coils, num_samples))
                processed_im = rng.random(size=(num_coils, num_samples))
                rx_data.append(
                    RxData(
                        index=int(k_average * num_averages + k_acquisition),
                        total_averages=num_averages,
                        average_index=k_average,
                        num_samples=num_samples,
                        num_samples_raw=num_raw_samples,
                        num_samples_discard=0,
                        dwell_time=1 / 20e3,
                        dwell_time_raw=1 / 20e6,
                        phase_offset=0,
                        freq_offset=0,
                        larmor_frequency=2.0123e6,
                        demod_frequency=2.0123e6,
                        raw_data=rng.random(size=(num_coils, num_raw_samples)),
                        processed_data=processed_re + 1j * processed_im,
                        time_stamp=k_average * (num_averages + k_acquisition) * 0.67,
                    )
                )
        return rx_data

    return _factory


@pytest.fixture()
def rx_data_fid() -> RxData:
    """Generate RxData with artificial FID signal."""
    adc_duration = 6.4e-3
    adc_bandwidth = 20e3
    total_samples = int(adc_duration*adc_bandwidth)
    samples_discard = total_samples // 10
    adc_samples = int(total_samples - 2*samples_discard)
    f_larmor = 2.021e6
    f_offset = 0.
    f_spcm = 20e6
    t2 = 0.6e-3
    amplitude = 1.

    t = np.linspace(0, adc_duration, int(adc_duration*f_spcm))
    complex_envelope = amplitude * np.exp(-t / t2) * np.exp(2j * np.pi * f_offset * t)
    raw_data = np.real(complex_envelope * np.exp(2j * np.pi * f_larmor * t))

    return RxData(
        index=0,
        total_averages=1,
        average_index=1,
        num_samples=adc_samples,
        num_samples_raw=raw_data.size,
        num_samples_discard=samples_discard,
        dwell_time=1/adc_bandwidth,
        dwell_time_raw=1/f_spcm,
        phase_offset=0,
        freq_offset=0,
        larmor_frequency=f_larmor,
        demod_frequency=f_larmor,
        raw_data=raw_data[None, ...],
    )

@pytest.fixture()
def rx_data_trapezoid() -> RxData:
    """Generate RxData with trapezoid data used for system testing."""
    adc_duration = 6.e-3
    adc_bandwidth = 20e3
    total_samples = int(adc_duration*adc_bandwidth)
    samples_discard = total_samples // 10
    adc_samples = int(total_samples - 2*samples_discard)
    f_spcm = 20e6
    ramp_time = 100e-6

    num_samples_ramp = int(ramp_time * f_spcm)
    num_samples_flat = int(adc_duration*f_spcm - 2*num_samples_ramp)
    ramp = np.linspace(0., 1., num_samples_ramp)
    flat = np.ones(num_samples_flat)
    raw_data = np.concat([ramp, flat, ramp[::-1]])

    return RxData(
        index=0,
        total_averages=1,
        average_index=1,
        num_samples=adc_samples,
        num_samples_raw=raw_data.size,
        num_samples_discard=samples_discard,
        dwell_time=1/adc_bandwidth,
        dwell_time_raw=1/f_spcm,
        phase_offset=0,
        freq_offset=0,
        larmor_frequency=0.,
        demod_frequency=0.,
        raw_data=raw_data[None, ...],
    )


@pytest.fixture()
def test_spectrum() -> Callable:
    """Sinusoidal test signal."""
    rng = np.random.default_rng(seed=0)

    def _test_signal(num_samples: int, noise_scale: float) -> np.ndarray:
        x = np.linspace(-5, 5, num_samples)
        echo = np.exp(-(x**2) / 2) / np.sqrt(2 * np.pi) * 10
        noise = rng.normal(loc=0, scale=noise_scale, size=num_samples)

        return np.fft.fftshift(np.fft.fft(np.fft.fftshift(echo + noise)))

    return _test_signal


@pytest.fixture()
def test_sequence() -> pp.Sequence:
    """Construct a test sequence."""
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "test_sequence")
    seq.set_definition("label_float", 123.123)
    seq.set_definition("label_int", 123)
    seq.set_definition("label_str", "string")

    rf_sinc = pp.make_sinc_pulse(flip_angle=np.pi / 2, delay=system.rf_dead_time, use="excitation", system=system)
    rf_rect = pp.make_block_pulse(flip_angle=np.pi, duration=200e-6, delay=system.rf_dead_time, system=system)
    grad_trap = pp.make_trapezoid(channel="x", area=system.max_grad*5e-3, system=system)
    grad_arbi = pp.make_arbitrary_grad(
        channel="y",
        first=0.,
        last=0.,
        waveform=np.sin(np.linspace(0, 2*np.pi, 120))*25, # 50 mT max
        system=system,
    )
    label1 = pp.make_label(type="SET", label="LIN", value=1)
    label2 = pp.make_label(type="SET", label="PAR", value=2)
    label3 = pp.make_label(type="SET", label="ECO", value=3)
    label4 = pp.make_label(type="SET", label="REP", value=4)
    label5 = pp.make_label(type="SET", label="IMA", value=True)
    adc1 = pp.make_adc(num_samples=200, dwell=1e-5, delay=system.adc_dead_time, system=system)
    adc2 = pp.make_adc(num_samples=500, dwell=1e-5, delay=system.adc_dead_time, system=system)

    seq.add_block(rf_sinc)
    seq.add_block(grad_arbi, adc1)
    seq.add_block(rf_rect)
    seq.add_block(grad_trap, label1, label2)
    seq.add_block(pp.make_delay(4e-6), label3, label4)
    seq.add_block(adc2, label5)
    return seq


@pytest.fixture()
def acquisition_parameter() -> Generator[AcquisitionParameter, None, None]:
    """Construct acquisition parameter object for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield AcquisitionParameter(
            larmor_frequency=2.123e6,
            b1_scaling=5.432,
            gradient_offset=Dimensions(0, 100, 500),
            fov_scaling=Dimensions(0.5, 0.0, 0.9),
            channel_assignment=Dimensions(1, 2, 3),
            averaging_delay=1.01,
            state_filepath=tmpdir,
        )
