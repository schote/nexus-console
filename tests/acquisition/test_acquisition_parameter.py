"""Test functions for interface classes."""
import pytest

from console.interfaces.interface_acquisition_parameter import AcquisitionParameter, DDCMethod


params = dict(
    larmor_frequency=2.123e6,
    b1_scaling=5.432,
    gradien_offset=[0, 100, 500],
    fov_scaling=[0.5, 0.0, 0.9],
    num_averafes=2,
    averaging_delay=1.01,
)


# @pytest.mark.parametrize("")
# def test_acquisition_parameter_constructor():
#     global parameter
#     parameter = AcquisitionParameter(
        
#     )