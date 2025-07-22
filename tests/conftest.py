"""Test configuration file."""

from collections.abc import Callable

import numpy as np
import pypulseq as pp
import pytest

from console.interfaces.acquisition_parameter import AcquisitionParameter, Dimensions
from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.sequences.system_settings import system
from console.interfaces.rx_data import RxData


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
        num_coils: int
        num_samples: int
        num_acquisitions: int
        num_averages: int

    Returns
    -------
        Random acquisition data array with dimensions: [averages, coils, phase encoding, readout]
    """
    rng = np.random.default_rng(seed=0)

    def _factory(num_coils: int, num_samples: int, num_acquisitions: int, num_averages: int) -> list[RxData]:
        num_raw_samples = num_samples * 1000
        rx_data = []
        for k_average in range(num_averages):
            for k_acquisition in range(num_acquisitions):
                rx_data.append(
                    RxData(
                        index=int(k_average * num_averages + k_acquisition),
                        total_averages=num_averages,
                        average_index=k_average,
                        num_samples=num_samples,
                        num_samples_raw=num_raw_samples,
                        dwell_time=1 / 20e3,
                        dwell_time_raw=1 / 20e6,
                        phase_offset=0,
                        freq_offset=0,
                        raw_data=rng.random(size=(num_coils, num_raw_samples)),
                        time_stamp=np.datetime64('now'),
                    )
                )
        return rx_data

    return _factory


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
        state_filepath=".",
    )
