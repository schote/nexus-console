"""Test configuration file."""

from collections.abc import Callable

import numpy as np
import pypulseq as pp
import pytest

from console.interfaces.acquisition_parameter import AcquisitionParameter, Dimensions
from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.sequences.system_settings import system


@pytest.fixture()
def seq_provider() -> SequenceProvider:
    """Construct default sequence provider as fixture for testing."""
    return SequenceProvider(
        gradient_efficiency=[0.4, 0.4, 0.4],
        gpa_gain=[1.0, 1.0, 1.0],
        output_limits=[200, 6000, 6000, 6000],
        spcm_dwell_time=5e-8,
        rf_to_mvolt=5e-3,
        high_impedance=[False, True, True, True],
        system=system,
    )


@pytest.fixture()
def random_acquisition_data() -> Callable:
    """Construct random acquisition data using factory function.

    Arguments:
    num_averages: int, num_coils: int, num_pe: int, num_ro: int

    Returns
    -------
        Random acquisition data array with dimensions: [averages, coils, phase encoding, readout]
    """
    rng = np.random.default_rng(seed=0)

    def _random_acquisition_data(num_averages: int, num_coils: int, num_pe: int, num_ro: int) -> np.ndarray:
        re = rng.random(size=(num_averages, num_coils, num_pe, num_ro))
        im = rng.random(size=(num_averages, num_coils, num_pe, num_ro))
        return re + 1j * im

    return _random_acquisition_data


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
    seq = pp.Sequence()
    seq.set_definition("Name", "test_sequence")
    seq.add_block(pp.make_sinc_pulse(flip_angle=np.pi / 2))
    seq.add_block(pp.make_delay(10e-6))
    seq.add_block(pp.make_trapezoid(channel="x", area=5e-3))
    seq.add_block(
        pp.make_arbitrary_grad(channel="y", waveform=np.array([0, 200, 400, 400, 400, 600, 600, 400, 200, 0]))
    )
    seq.add_block(pp.make_adc(num_samples=200, dwell=1e-5))
    return seq


@pytest.fixture()
def acquisition_parameter() -> AcquisitionParameter:
    """Construct acquisition parameter object for testing."""
    return AcquisitionParameter(
        larmor_frequency=2.123e6,
        b1_scaling=5.432,
        gradient_offset=Dimensions(0, 100, 500),
        fov_scaling=Dimensions(0.5, 0.0, 0.9),
        averaging_delay=1.01,
        default_state_file_path=".",
    )
