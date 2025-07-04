"""Test (ISMR)MRD export."""
import os

import numpy as np
import pytest

from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.rx_data import RxData
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
    dummy_data = np.zeros((1, 128), dtype=complex)
    dummy_data[0, :] = (np.random.default_rng().random(128) + 1j * np.random.default_rng().random(128))

    f0 = 2.0123e6
    receive_data = []
    receive_data.append([
        RxData(
            index=1,
            num_pnts=128,
            dwell_time=1 / 20e3,
            dwell_time_raw=1 / 20e6,
            phase_offset=0,
            freq_offset=0,
            larmor_frequency=f0,
            processed_data=dummy_data
        ),
        RxData(
            index=1,
            num_pnts=128,
            dwell_time=1 / 20e3,
            dwell_time_raw=1 / 20e6,
            phase_offset=0,
            freq_offset=0,
            larmor_frequency=f0,
            processed_data=dummy_data
        )
    ])

    acq_data = AcquisitionData(
        receive_data=receive_data,
        acquisition_parameters=AcquisitionParameter(larmor_frequency=f0),
        sequence=seq,
        dwell_time=1e-5,
        session_path=os.path.join("tmp", "")
    )

    acq_data.save_ismrmrd(header=header)

    # TODO: Load header and check f0
