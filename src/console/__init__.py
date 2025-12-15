"""Console package init file."""
import logging

from console.interfaces.acquisition_parameter import AcquisitionParameter


parameter = AcquisitionParameter.load()

if not parameter:
    log = logging.getLogger("AcqParam")
    log.warning(
        "Could not load AcquisitionParameter state."
        "\nUsing default parameter configuration...",
    )
    parameter = AcquisitionParameter()
    print(parameter)
