"""Test functions for acquisition parameter."""
import copy

from console.interfaces.acquisition_parameter import AcquisitionParameter


def test_save_load(acquisition_parameter: AcquisitionParameter) -> None:
    """Check if saved acquisition parameter correspond to loaded acquisition parameter."""
    acquisition_parameter.save()
    params_check = AcquisitionParameter.load(".")
    assert isinstance(params_check, AcquisitionParameter)
    assert params_check == acquisition_parameter


def test_autosave(acquisition_parameter: AcquisitionParameter) -> None:
    """Check auto-save methods."""
    params_copy = copy.deepcopy(acquisition_parameter)
    assert params_copy == acquisition_parameter

    params_copy.save_on_mutation = False
    params_copy.larmor_frequency = 1.23456e6
    assert params_copy != AcquisitionParameter.load(params_copy.default_state_file_path)

    params_copy.save_on_mutation = True
    params_copy.larmor_frequency = 9.87654e6
    assert params_copy == AcquisitionParameter.load(params_copy.default_state_file_path)
