"""Console package init file."""
import logging

from console.interfaces.acquisition_parameter import AcquisitionParameter


_parameter: AcquisitionParameter | None = AcquisitionParameter.load()
parameter: AcquisitionParameter

if isinstance(_parameter, AcquisitionParameter):
    parameter = _parameter
else:
    log = logging.getLogger("AcqParam")
    log.warning(
        "Could not load AcquisitionParameter state."
        "\nUsing default parameter configuration...",
    )
    parameter = AcquisitionParameter()
    print(parameter)
