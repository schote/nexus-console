"""Implementation of nexus acquisition manager for multiprocessing."""
import traceback
import console
from multiprocessing.managers import BaseManager
from console.spcm_control.acquisition_control import AcquisitionControl

from console.interfaces.dimensions import Dimensions
from console.interfaces.enums import DDCMethod


class AcquisitionParameterProxy:
    
    def get_larmor_frequency(self) -> float:
        return console.parameter.larmor_frequency

    def set_larmor_frequency(self, value: float) -> None:
        console.parameter.larmor_frequency = value
    
    def get_b1_scaling(self) -> float:
        return console.parameter.b1_scaling

    def set_b1_scaling(self, value: float) -> None:
        console.parameter.b1_scaling = value
    
    def get_gradient_offset(self) -> Dimensions:
        return console.parameter.gradient_offset

    def set_gradient_offset(self, value: Dimensions) -> None:
        console.parameter.gradient_offset = value

    def get_fov_scaling(self) -> Dimensions:
        return console.parameter.fov_scaling

    def set_fov_scaling(self, value: Dimensions) -> None:
        console.parameter.fov_scaling = value
        
    def get_decimation(self) -> int:
        return console.parameter.decimation

    def set_decimation(self, value: int) -> None:
        console.parameter.decimation = value

    def get_ddc_method(self) -> DDCMethod:
        return console.parameter.ddc_method

    def set_ddc_method(self, value: DDCMethod) -> None:
        console.parameter.ddc_method = value

    def get_num_averages(self) -> int:
        return console.parameter.num_averages

    def set_num_averages(self, value: int) -> None:
        console.parameter.num_averages = value

    def get_averaging_delay(self) -> float:
        return console.parameter.averaging_delay

    def set_averaging_delay(self, value: float) -> None:
        console.parameter.averaging_delay = value    


class AcquisitionControlManager(BaseManager):
    def __init__(
        self,
        address=('localhost', 50000),
        authkey=b'secretkey',
        callable_acq_control=None,
        callable_acq_parameter=None,
        *args, **kwargs
    ):
        super().__init__(address=address, authkey=authkey, *args, **kwargs)
        # Register acquisition control, the process which starts the manager needs a callable
        if callable_acq_control:
            self.register('AcquisitionControl', callable=callable_acq_control)
        else:
            self.register('AcquisitionControl')
        
        if callable_acq_parameter:
            self.register('AcquisitionParameterProxy', callable=callable_acq_parameter)
        else:
            self.register('AcquisitionParameterProxy')

    def __enter__(self) -> tuple[AcquisitionControl, AcquisitionParameterProxy]:
        """Enter with context."""
        try:
            self.connect()
            self.acq_control: AcquisitionControl = self.AcquisitionControl()  # Obtain the proxy
            # self.acq_parameter: AcquisitionParameter = self.AcquisitionParameter()
            self.acq_parameter: AcquisitionParameterProxy = self.AcquisitionParameterProxy()
            return (self.acq_control, self.acq_parameter)
            # return (self.AcquisitionControl(), self.AcquisitionParameterProxy())
        except Exception as e:
            print(f"Error connecting to AcquisitionControlManager: {e}")
            raise
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        "Exit with context."
        # Explicitly remove the proxy references
        if hasattr(self, "acq_control"):
            del self.acq_control
        if hasattr(self, "acq_parameter"):
            del self.acq_parameter

        if exc_type is not None:
            print(f"An error occurred: {exc_value}")
            traceback.print_tb(exc_tb)

        return False  # Propagate exceptions if they occur