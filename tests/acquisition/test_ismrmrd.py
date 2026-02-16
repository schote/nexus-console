"""Test (ISMR)MRD export."""
import tempfile
from pathlib import Path

import ismrmrd
import numpy as np
import pytest

from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.dimensions import Dimensions
from console.utilities.data import write_acquisition_to_mrd
from console.utilities.sequences import se_spectrum, tse_3d


@pytest.mark.parametrize("trajectory_type", [tse_3d.Trajectory.INOUT, tse_3d.Trajectory.LINEAR])
@pytest.mark.parametrize("dim", [
    Dimensions(x=60, y=50, z=20),   # 3D case
    Dimensions(x=100, y=80, z=1),   # 2D case
    Dimensions(x=119, y=1, z=1),    # 1D case
])
def test_write_acquisition_to_mrd(trajectory_type, dim, random_complex_data, acquisition_parameter, seq_provider):
    """Test saving acquisition data from 3D TSE sequence to mrd."""
    seq, header = tse_3d.constructor(
        n_enc=dim,
        fov=Dimensions(x=120, y=100, z=80),
        channel_ro="x",
        channel_pe1="y",
        channel_pe2="z",
        trajectory=trajectory_type,
    )

    seq_provider.from_pypulseq(seq)
    unrolled_sequence = seq_provider.unroll_sequence(acquisition_parameter)
    receive_data = unrolled_sequence.rx_data

    for k, rx_data in enumerate(receive_data):
        rx_data.processed_data = random_complex_data(shape=(1, rx_data.num_samples))
        rx_data.time_stamp = k * 10

    tmp_dir = tempfile.mkdtemp()
    acq_data = AcquisitionData(
        receive_data=receive_data,
        acquisition_parameters=acquisition_parameter,
        sequence=seq_provider.to_pypulseq(),
        session_path=tmp_dir,
    )

    acq_data.save_ismrmrd(header=header)

    acq_folder = Path(tmp_dir) / acq_data.meta["folder_name"]
    acq_data_files = [f.name for f in acq_folder.iterdir() if f.is_file()]
    assert "data.mrd" in acq_data_files

    with ismrmrd.File(acq_folder / "data.mrd", 'r') as fh:
        dataset = fh['dataset']
        acquisitions = dataset.acquisitions[:]

    assert len(acquisitions) == len(receive_data)
    for k in range(len(acquisitions)):
        np.testing.assert_array_almost_equal(acquisitions[k].data, receive_data[k].processed_data)


@pytest.mark.parametrize("num_coils", [1, 2, 4])
@pytest.mark.parametrize("num_averages", [1, 5])
def test_write_single_acquisition_to_mrd(random_acquisition_data, num_coils: int, num_averages: int) -> None:
    """Test ismrmrd export for single 1D data acquisition."""
    num_samples = 1000
    receive_data = random_acquisition_data(
        num_coils=num_coils,
        num_samples=num_samples,
        num_acquisitions=1,
        num_averages=num_averages,
    )

    header = ismrmrd.xsd.ismrmrdHeader()
    header.experimentalConditions = ismrmrd.xsd.experimentalConditionsType(receive_data[0].larmor_frequency)

    channel_assignment = Dimensions(x=1, y=2, z=3)

    tmp_dir = tempfile.mkdtemp()
    mrd_path = write_acquisition_to_mrd(
        data=receive_data,
        header=header,
        dataset_path=Path(tmp_dir) / "raw_data.mrd",
        sequence=se_spectrum.constructor(num_samples=num_samples),
        channel_assignment = channel_assignment,
    )

    with ismrmrd.File(mrd_path, 'r') as fh:
        dataset = fh['dataset']
        acquisitions = dataset.acquisitions[:]

    assert len(acquisitions) == len(receive_data)
    for k in range(len(acquisitions)):
        np.testing.assert_array_almost_equal(acquisitions[k].data, receive_data[k].processed_data)
