"""Global acquisition parameter."""
import os

from console.interfaces.interface_acquisition_parameter import DEFAULT_STATE_FILE_PATH, AcquisitionParameter

# Load state of acquisition parameters from file, if it exists
if os.path.exists(DEFAULT_STATE_FILE_PATH):
    print("Default file path: ", DEFAULT_STATE_FILE_PATH)
    parameter = AcquisitionParameter.load()
else:
    parameter = AcquisitionParameter()


def update_parameters(**change) -> None:
    """Update global acquisition parameter variable."""
    global parameter
    parameter = parameter.update(**change)
