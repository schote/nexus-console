"""Test functions for acquisition parameter."""
from console.interfaces.interface_acquisition_parameter import AcquisitionParameter


def test_save_load(acquisition_parameter):
    """Check if saved acquisition parameter correspond to loaded acquisition parameter."""
    acquisition_parameter.save()
    params_check = AcquisitionParameter.load(".")
    assert isinstance(params_check, AcquisitionParameter)
    assert params_check == acquisition_parameter
