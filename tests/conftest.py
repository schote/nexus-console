"""Test configuration file."""
import numpy as np
import pypulseq as pp
import pytest

from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.sequences.system_settings import system


@pytest.fixture
def seq_provider():
    """Construct default sequence provider as fixture for testing."""
    return SequenceProvider(
        gradient_efficiency=[.4, .4, .4],
        gpa_gain=[1.0, 1.0, 1.0],
        output_limits=[200, 6000, 6000, 6000],
        spcm_dwell_time=5e-8,
        rf_to_mvolt=5e-3,
        high_impedance=[False, True, True, True]
        system=system
    )

@pytest.fixture
def random_acquisition_data():
    """Construct random acquisition data using factory function.

    Arguments:
    num_averages: int, num_coils: int, num_pe: int, num_ro: int

    Returns
    -------
        Random acquisition data array with dimensions: [averages, coils, phase encoding, readout]
    """
    np.random.seed(seed=0)
    def _random_acquisition_data(num_averages: int, num_coils: int, num_pe: int, num_ro: int):
        re = np.random.rand(num_averages, num_coils, num_pe, num_ro)
        im = np.random.rand(num_averages, num_coils, num_pe, num_ro)
        return re + 1j * im
    return _random_acquisition_data

@pytest.fixture
def test_spectrum():
    """Sinusoidal test signal."""
    np.random.seed(seed=0)
    def _test_signal(num_samples: int, noise_scale: float):
        x = np.linspace(-5, 5, num_samples)
        echo = np.exp(-x**2/2) / np.sqrt(2*np.pi) * 10
        noise = np.random.normal(loc=0, scale=noise_scale, size=num_samples)

        spcm = np.fft.fftshift(np.fft.fft(np.fft.fftshift(echo + noise)))

        return spcm
    return _test_signal


@pytest.fixture
def test_sequence():
    """Construct a test sequence."""
    seq = pp.Sequence()
    seq.set_definition("Name", "test_sequence")
    seq.add_block(pp.make_sinc_pulse(flip_angle=np.pi/2))
    seq.add_block(pp.make_delay(10e-6))
    seq.add_block(pp.make_trapezoid(channel="x", area=5e-3))
    seq.add_block(
        pp.make_arbitrary_grad(channel="y", waveform=np.array([0, 200, 400, 400, 400, 600, 600, 400, 200, 0]))
    )
    seq.add_block(pp.make_adc(num_samples=200, dwell=1e-5))
    return seq
