"""Test digital down converter (DDC) functions."""
import numpy as np
import pytest
from scipy import signal

from console.utilities.ddc import filter_cic_fir_comp, filter_moving_average


@pytest.mark.parametrize("coils", [1, 2, 4])
@pytest.mark.parametrize("phase_encoding", [1, 16])
@pytest.mark.parametrize("num_samples", [8000, 9511])
@pytest.mark.parametrize("decimation", [100, 200, 400])
@pytest.mark.parametrize("overlap", [2, 4])
def test_moving_average_filter(coils, phase_encoding, num_samples, decimation, overlap, random_acquisition_data):
    """Test moving average filter for various parameter configurations with FIR as reference."""
    input_data = random_acquisition_data(1, coils, phase_encoding, num_samples)
    processed_avg = filter_moving_average(input_data, decimation=decimation, overlap=overlap)
    processed_fir = signal.decimate(input_data, q=decimation, ftype="fir")

    assert processed_avg.shape == processed_fir.shape
    assert np.iscomplex(processed_avg).all()
    assert np.iscomplex(processed_fir).all()


@pytest.mark.parametrize("coils", [1, 2, 4])
@pytest.mark.parametrize("phase_encoding", [1, 16])
@pytest.mark.parametrize("num_samples", [8000, 9511])
@pytest.mark.parametrize("decimation", [100, 200, 400])
@pytest.mark.parametrize("filter_stages", [2, 3, 5])
def test_cic_fir_comp(coils, phase_encoding, num_samples, decimation, filter_stages, random_acquisition_data):
    """Test CIC FIR filter composition with FIR as reference."""
    input_data = random_acquisition_data(1, coils, phase_encoding, num_samples)
    processed_cic = filter_cic_fir_comp(input_data, decimation=decimation, number_of_stages=filter_stages)
    processed_fir = signal.decimate(input_data, q=decimation, ftype="fir")

    assert processed_cic.shape == processed_fir.shape
    assert np.iscomplex(processed_cic).all()


@pytest.mark.parametrize("num_raw_samples", [80640, 128000])
def test_decimated_shapes(num_raw_samples, random_acquisition_data):
    """Test shape of decimated signals.

    It is tested if two random signals have the same shape after decimation
    with moving average filter and scipy's fir filter for a range of
    decimation factors from 200 ... 1000.
    """
    input_data = random_acquisition_data(1, 1, 1, num_raw_samples)
    decimation_factors = np.arange(200, 1000, 1)
    for d in decimation_factors:
        data_avg = filter_moving_average(input_data, decimation=d, overlap=8)
        data_fir = signal.decimate(input_data, q=d, ftype="fir")
        assert data_fir.shape == data_avg.shape
