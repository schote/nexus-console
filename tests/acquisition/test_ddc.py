"""Test digital down converter (DDC) functions."""
import numpy as np
import pytest
from scipy import signal

from console.utilities.ddc import filter_cic_fir_comp, filter_moving_average


@pytest.mark.parametrize("num_coils", [1, 2, 4])
@pytest.mark.parametrize("num_samples", [8000, 9511, 80640])
@pytest.mark.parametrize("decimation", [100, 200, 400])
@pytest.mark.parametrize("overlap", [2, 4])
def test_moving_average_filter(num_coils, num_samples, decimation, overlap, random_complex_data):
    """Test moving average filter for various parameter configurations with FIR as reference."""
    input_data = random_complex_data(shape=(num_coils, num_samples))
    processed_avg = filter_moving_average(input_data, decimation=decimation, overlap=overlap)
    processed_fir = signal.decimate(input_data, q=decimation, ftype="fir")

    assert processed_avg.shape == processed_fir.shape
    assert np.iscomplex(processed_avg).all()
    assert np.iscomplex(processed_fir).all()


@pytest.mark.parametrize("num_coils", [1, 2, 4])
@pytest.mark.parametrize("num_samples", [8000, 9511, 80640])
@pytest.mark.parametrize("decimation", [100, 200, 400])
@pytest.mark.parametrize("filter_stages", [2, 3, 5])
def test_cic_fir_comp(num_coils, num_samples, decimation, filter_stages, random_complex_data):
    """Test CIC FIR filter composition with FIR as reference."""
    input_data = random_complex_data(shape=(num_coils, num_samples))
    processed_cic = filter_cic_fir_comp(input_data, decimation=decimation, number_of_stages=filter_stages)
    processed_fir = signal.decimate(input_data, q=decimation, ftype="fir")

    assert processed_cic.shape == processed_fir.shape
    assert np.iscomplex(processed_cic).all()


@pytest.mark.parametrize("fixture_name", ["rx_data_fid", "rx_data_trapezoid"])
def test_rx_data_processing(fixture_name, request):
    """Test RxData processing."""
    rx_data = request.getfixturevalue(fixture_name)
    rx_data.process_data(store_unprocessed=True)

    # Get the envelope of the raw signal using the Hilbert transform and discard samples
    raw_envelope = signal.hilbert(rx_data.raw_data[0])
    processed = rx_data.processed_data[0]

    if rx_data.num_samples_discard > 0:
        processed = processed[rx_data.num_samples_discard:-rx_data.num_samples_discard]
        discard_raw = int(rx_data.num_samples_discard * rx_data.decimation_factor)
        raw_envelope = raw_envelope[discard_raw:-discard_raw]

    # Compare the 99th percentile of the absolute signals
    val_raw = np.percentile(np.abs(raw_envelope), 99)
    val_proc = np.percentile(np.abs(processed), 99)
    np.testing.assert_allclose(val_proc, val_raw, rtol=0.01)
