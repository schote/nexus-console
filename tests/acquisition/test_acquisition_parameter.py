"""Test functions for acquisition parameter."""
import os
import shutil
import subprocess
import sys
from copy import copy
from pathlib import Path

import pytest

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


def test_load_binds_to_file(acquisition_parameter: AcquisitionParameter, tmp_path: Path) -> None:
    """Check that a loaded instance syncs with the file it was loaded from, not the path stored in it."""
    acquisition_parameter.save()
    copied = tmp_path / "copy.state"
    shutil.copy(acquisition_parameter.state_filepath, copied)
    params_copy = AcquisitionParameter.load(copied)
    assert params_copy is not None
    assert params_copy.state_filepath == str(copied)
    params_copy.larmor_frequency = 1.234e6
    assert AcquisitionParameter.load(copied) == params_copy
    assert AcquisitionParameter.load(acquisition_parameter.state_filepath) == acquisition_parameter


def test_load_missing_file(tmp_path: Path) -> None:
    """Check that loading a missing file returns defaults bound to that path and writes only on mutation."""
    path = tmp_path / "missing.state"
    params = AcquisitionParameter.load(path)
    assert params == AcquisitionParameter(state_filepath=str(path))
    assert not path.exists()
    params.num_averages = 4
    assert AcquisitionParameter.load(path) == params


def test_import_has_no_side_effect(tmp_path: Path) -> None:
    """Check that importing the console package does not write the state file."""
    subprocess.run(
        [sys.executable, "-c", "import console.spcm_control.acquisition_control"],
        env={**os.environ, "HOME": str(tmp_path)},
        check=True,
    )
    assert not (tmp_path / "nexus-console").exists()


def test_invalid_attribute(acquisition_parameter: AcquisitionParameter) -> None:
    """Ensure that TypeError is raised when invalid value is set."""
    with pytest.raises(TypeError):
        acquisition_parameter.larmor_frequency = [1, 2, 3]
    with pytest.raises(TypeError):
        acquisition_parameter.b1_scaling = [1, 2, 3]
    with pytest.raises(TypeError):
        acquisition_parameter.gradient_offset = 2.
    with pytest.raises(TypeError):
        acquisition_parameter.fov_scaling = 2.
