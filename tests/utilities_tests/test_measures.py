"""Test measure funtions defined like SNR."""
import pytest

from console.utilities.snr import signal_to_noise_ratio


@pytest.mark.parametrize("noise_snr", [
    (0.2, 41.1),
    (0.5, 32.7),
    (1.0, 26.8)
])
def test_snr_calculation(noise_snr, test_spectrum):
    """Test snr calculation."""
    num_samples = 400
    dwell_time = 4e-3/num_samples
    noise_scale, snr_result = noise_snr
    spectrum_data = test_spectrum(num_samples, noise_scale)

    snr = signal_to_noise_ratio(spectrum_data, dwell_time=dwell_time)

    assert snr == pytest.approx(snr_result, abs=0.8)
