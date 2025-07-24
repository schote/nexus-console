"""Test (ISMR)MRD export."""
import tempfile
from pathlib import Path

import pytest

from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.dimensions import Dimensions
from console.utilities.sequences import tse_3d


@pytest.mark.parametrize("trajectory_type", [tse_3d.Trajectory.INOUT, tse_3d.Trajectory.LINEAR])
@pytest.mark.parametrize("dim", [Dimensions(x=60, y=50, z=20)])
def test_tse_3d(trajectory_type, dim, random_complex_data, acquisition_parameter, seq_provider):
    """Test 3D TSE imaging sequence constructor."""
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
