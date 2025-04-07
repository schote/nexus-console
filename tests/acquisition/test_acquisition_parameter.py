"""Test functions for acquisition parameter."""
from copy import copy

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.enums import DDCMethod


def test_save_load(acquisition_parameter: AcquisitionParameter) -> None:
    """Check if saved acquisition parameter correspond to loaded acquisition parameter."""
    acquisition_parameter.save()
    params_check = AcquisitionParameter.load(acquisition_parameter.state_filepath)
    assert isinstance(params_check, AcquisitionParameter)
    assert params_check == acquisition_parameter


def test_autosave(acquisition_parameter: AcquisitionParameter) -> None:
    """Check auto-save methods."""
    params_copy = copy(acquisition_parameter)
    assert params_copy == acquisition_parameter

    # Test autosave
    params_copy.larmor_frequency = 9.87654e6
    params_copy.gradient_offset = params_copy.gradient_offset * 2
    params_copy.fov_scaling = params_copy.fov_scaling - 0.1
    params_copy.ddc_method = DDCMethod.CIC
    assert params_copy == AcquisitionParameter.load(params_copy.state_filepath)
