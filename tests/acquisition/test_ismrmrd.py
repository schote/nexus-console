"""Test (ISMR)MRD export."""
import os

import pytest

from console.interfaces.interface_acquisition_data import AcquisitionData
from console.interfaces.interface_acquisition_parameter import AcquisitionParameter
from console.utilities import sequences


@pytest.mark.parametrize("dim", [sequences.Dimensions(16, 64, 64)])
@pytest.mark.parametrize("fov", [sequences.Dimensions(100, 100, 50)])
def test_tse_3d(fov, dim, random_acquisition_data):
    """Test 3D TSE imaging sequence constructor."""
    seq, header = sequences.tse_3d.constructor(
        n_enc=dim,
        fov=fov,
        trajectory=sequences.tse_3d.Trajectory.INOUT
    )

    f0 = 2.0123e6

    acq_data = AcquisitionData(
        _raw=[random_acquisition_data(1, 1, dim.x*dim.z, dim.y)],
        acquisition_parameters=AcquisitionParameter(larmor_frequency=f0),
        sequence=seq,
        dwell_time=1e-5,
        session_path=os.path.join("tmp", "")
    )

    acq_data.save_ismrmrd(header=header)

    # TODO: Load header and check f0
