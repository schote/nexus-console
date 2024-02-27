"""Global acquisition parameter."""
import copy
import os

# import dataclasses
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter

# Load state of acquisition parameters from file, if it exists
parameter = AcquisitionParameter().load() if os.path.exists("acq-param-state.pkl") else AcquisitionParameter()


def get_copy() -> AcquisitionParameter:
    """Return copy of acquisition parameter object."""
    return copy.deepcopy(parameter)

# def set_value(changes: dict) -> None:
#     global parameter
#     parameter = dataclasses.replace(parameter, **changes)

# Changes to dataclass:
# parameter = dataclasses.replace(parameter, larmor_frequency=2.1e6)
