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
    )

    # Check if info is appended to meta
    info = {"test": "test"}
    acq_data.add_info(info)
    assert info == acq_data.meta["info"]

    rng = np.random.default_rng(seed=0)
    additional_data_key = "test-data"
    acq_data.add_data({additional_data_key: rng.random(size=(1, 10, 100))})

    # Check if meta and sequence is saved
    acq_data.save(user_path=tmp_dir)
    acq_folder = Path(tmp_dir) / acq_data.meta["folder_name"]
    acq_data_files = [f.name for f in acq_folder.iterdir() if f.is_file()]

    assert "meta.json" in acq_data_files
    assert "sequence.seq" in acq_data_files
    assert f"{additional_data_key}.npy" in acq_data_files


def test_acquisition_data_default_path(
    acquisition_parameter, test_sequence, random_acquisition_data, monkeypatch, tmp_path
):
    """Without a user path the data is saved to the session folder in the caller's home directory."""
    receive_data = random_acquisition_data(num_coils=1, num_samples=50, num_acquisitions=1, num_averages=1)
    for rx_obj in receive_data:
        rx_obj.process_data(store_unprocessed=False)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    acq_data = AcquisitionData(
        receive_data=receive_data,
        acquisition_parameters=acquisition_parameter,
        sequence=test_sequence,
    )
    acq_data.save()

    session_folders = list((tmp_path / "nexus-console").glob("*-session"))
    assert len(session_folders) == 1
    assert session_folders[0].name == f"{acq_data.meta['date']}-session"
    assert (session_folders[0] / acq_data.meta["folder_name"] / "meta.json").is_file()
