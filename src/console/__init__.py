"""Console package init file."""
from console.interfaces.acquisition_parameter import AcquisitionParameter

parameter: AcquisitionParameter


def __getattr__(name: str) -> AcquisitionParameter:
    """Load the acquisition parameter state on first access of `console.parameter`."""
    if name != "parameter":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    global parameter
    parameter = AcquisitionParameter.load() or AcquisitionParameter()
    return parameter
