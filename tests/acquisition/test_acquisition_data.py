"""Test functions for interface classes."""
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from console.interfaces.acquisition_data import AcquisitionData


def test_acquisition_data(acquisition_parameter, test_sequence, random_acquisition_data):
    """Test acquisition data."""
    receive_data = random_acquisition_data(
        num_coils=1,
        num_samples=50,
        num_acquisitions=3,
        num_averages=2,
    )
    for rx_data in receive_data:
        rx_data.larmor_frequency = acquisition_parameter.larmor_frequency

    # Process receive data
    with ThreadPoolExecutor() as executor:
        executor.map(
            lambda rx_obj: rx_obj.process_data(store_unprocessed=False),
            receive_data
        )

    # Generate acquisition data
    tmp_dir = tempfile.mkdtemp()
    acq_data = AcquisitionData(
        receive_data=receive_data,
        acquisition_parameters=acquisition_parameter,
        sequence=test_sequence,
        session_path=tmp_dir,
    )

    # Check if info is appended to meta
    info = {"test": "test"}
    acq_data.add_info(info)
    assert info == acq_data.meta["info"]

    rng = np.random.default_rng(seed=0)
    additional_data_key = "test-data"
    acq_data.add_data({additional_data_key: rng.random(size=(1, 10, 100))})

    # Check if meta and sequence is saved
    acq_data.save()
    acq_folder = Path(tmp_dir) / acq_data.meta["folder_name"]
    acq_data_files = [f.name for f in acq_folder.iterdir() if f.is_file()]

    assert "meta.json" in acq_data_files
    assert "sequence.seq" in acq_data_files
    assert f"{additional_data_key}.npy" in acq_data_files
