"""Test functions for interface classes."""
import os

from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter


def test_acquisition_data(test_sequence, random_acquisition_data):
    """Test acquisition data."""
    params = AcquisitionParameter(
        larmor_frequency=2.0e6
    )

    assert isinstance(params.dict(), dict)

    acq_data = AcquisitionData(
        _raw=[random_acquisition_data(1, 1, 1, 128)],
        acquisition_parameters=params,
        sequence=test_sequence,
        dwell_time=1e-5
    )

    info = {"test": "test"}
    acq_data.add_info(info)

    assert info == acq_data.meta["info"]

    acq_data.write("./tmp/")
    acq_data_files = list(os.walk("./tmp/"))[-1][-1]

    assert "meta.json" in acq_data_files
    assert "raw_data.npy" in acq_data_files
    assert "sequence.seq" in acq_data_files
