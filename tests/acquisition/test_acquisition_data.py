"""Test functions for interface classes."""
import os

from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.rx_data import RxData


def test_acquisition_data(test_sequence, random_acquisition_data):
    """Test acquisition data."""
    params = AcquisitionParameter(
        larmor_frequency=2.0e6
    )

    assert isinstance(params.dict(), dict)

    receive_data = []
    receive_data.append([
        RxData(
            index=1,
            num_samples=120,
            num_samples_raw=120000,
            dwell_time=1 / 20e3,
            dwell_time_raw=1 / 20e6,
            phase_offset=0,
            freq_offset=0,
            total_averages=2,
            average_index=0,
        ),
        RxData(
            index=1,
            num_samples=120,
            num_samples_raw=120000,
            dwell_time=1 / 20e3,
            dwell_time_raw=1 / 20e6,
            phase_offset=0,
            freq_offset=0,
            total_averages=2,
            average_index=1,
        )
    ])

    acq_data = AcquisitionData(
        receive_data=receive_data,
        acquisition_parameters=params,
        sequence=test_sequence,
        session_path=r"./tmp"
    )

    info = {"test": "test"}
    acq_data.add_info(info)

    assert info == acq_data.meta["info"]

    acq_data.save("./tmp/")
    acq_data_files = list(os.walk("./tmp/"))[-1][-1]

    assert "meta.json" in acq_data_files
    assert "sequence.seq" in acq_data_files
