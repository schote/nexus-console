"""Test digital down converter (DDC) functions."""
import numpy as np
import pytest

from console.utilities.ddc import filter_cic_fir_comp, filter_moving_average


@pytest.mark.parametrize("coils", [1, 2, 4])
@pytest.mark.parametrize("phase_encoding", [1, 16])
@pytest.mark.parametrize("num_samples", [8000, 9511])
@pytest.mark.parametrize("decimation", [100, 200, 400])
@pytest.mark.parametrize("overlap", [2, 4])
def test_moving_average_filter(coils, phase_encoding, num_samples, decimation, overlap, random_acquisition_data):
    """Test moving average filter for various parameter configurations."""
    input_data = random_acquisition_data(1, coils, phase_encoding, num_samples)
    processed = filter_moving_average(input_data, decimation=decimation, overlap=overlap)

    proc_avg, proc_coils, proc_pe, proc_samples = processed.shape

    assert proc_avg == 1
    assert proc_coils == coils
    assert proc_pe == phase_encoding
    assert proc_samples == num_samples // decimation
    assert np.iscomplex(processed).all()


@pytest.mark.parametrize("coils", [1, 2, 4])
@pytest.mark.parametrize("phase_encoding", [1, 16])
@pytest.mark.parametrize("num_samples", [8000, 9511])
@pytest.mark.parametrize("decimation", [100, 200, 400])
@pytest.mark.parametrize("filter_stages", [2, 3, 5])
def test_cic_fir_comp(coils, phase_encoding, num_samples, decimation, filter_stages, random_acquisition_data):
    """Test CIC FIR filter composition."""
    input_data = random_acquisition_data(1, coils, phase_encoding, num_samples)
    processed = filter_cic_fir_comp(input_data, decimation=decimation, number_of_stages=filter_stages)

    proc_avg, proc_coils, proc_pe, proc_samples = processed.shape

    assert proc_avg == 1
    assert proc_coils == coils
    assert proc_pe == phase_encoding
    assert proc_samples == num_samples // decimation
    assert np.iscomplex(processed).all()
