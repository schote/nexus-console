"""Console package init file."""
import logging

from console.interfaces.acquisition_parameter import AcquisitionParameter

if (parameter := AcquisitionParameter.load()) is None:
    log = logging.getLogger("AcqParam")
    log.warning(
        "Could not load AcquisitionParameter state."
        "\nUsing default parameter configuration...",
    )
    parameter = AcquisitionParameter()
