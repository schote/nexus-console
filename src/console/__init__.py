"""Console package init file."""
from console.interfaces.acquisition_parameter import AcquisitionParameter

acq_parameter: AcquisitionParameter = AcquisitionParameter()

def load_state(state_file_path: str) -> None:
    global acq_parameter
    try:
        acq_parameter = AcquisitionParameter.load(state_file_path)
    except FileNotFoundError as exc:
        self.log.warning("Acquisition parameter state could not be loaded from dir: %s.\
            Creating new acquisition parameter object.", exc)
        acq_parameter = AcquisitionParameter()