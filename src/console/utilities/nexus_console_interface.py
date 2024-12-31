from console.spcm_control.acquisition_control import AcquisitionControl
from console.interfaces.acquisition_data import AcquisitionData
import console
import os

class NexusConsoleInterface():
    
    def __init__(self, device_config_file):
        self.status             = "inactive"
        self.device_config_file = device_config_file
        self.console            = None
        self.user_path          = None
    
    def get_parameter(self, param : str = None):
        """ Get parameters from the console, if no parameter is specified then return dict of all parameters
        TODO: Handle unknown variable name properly
        """
        if self.console is not None:
            print("Attempting to get console parameters")
            params_dict = console.parameter.dict()
            print(params_dict)
            if param is not None or param != "":
                """Return value of requested parameter"""
                if param in params_dict.keys():
                    return params_dict[param]
                elif param == "sample_rate": #not a console parameter but handy to have access to for setting decimation
                    return self.console.rx_card.sample_rate
                else:
                    print("Handle param not found")
            else:
                return params_dict
        else:
            print("Handle error if console is not initialised")
    
    def set_parameter(self, param : str, value):
        """Set the console parameter to the passed variable
        TODO: Handle unknown parameter name
        TODO: Check variable typing and handle invalid types
        """
        if self.console is not None:
            if param == "larmor_frequency":
                if isinstance(value, (int, float)):
                    console.parameter.larmor_frequency = value
                else:
                    print("Invalid data type for larmor frequency, handle")
            elif param == "b1_scaling":
                if isinstance(value, float):
                    console.parameter.b1_scaling = value
                else:
                    print("Invalid data type for b1 scaling, handle")
            elif param == "gradient_scaling":
                print("gradient scaling is not yet implemented")
            elif param == "fov_scaling":
                print("gradient scaling is not yet implemented")
            elif param == "decimation":
                if isinstance(value, int):
                    console.parameter.decimation = value
                else:
                    print("Invalid data type for decimation, handle")
            elif param == "num_averages":
                if isinstance(value, int):
                    console.parameter.num_averages = value
                else:
                    print("Invalid data type for number of averages handle")
            elif param == "averaging_delay":
                if isinstance(value, float):
                    console.parameter.averaging_delay = value
                else:
                    print("Invalid data type for averaging delay,  handle")
            elif param == "default_state_file_path":
                print("default_state_file_path not yet implemented")
            elif param == "save_on_mutation":
                if isinstance(value, bool):
                    console.parameter.save_on_mutation = value
                else:
                    print("Invalid data type for save on mutation,  handle")
            else:
                print("Need to handle invalid parameter name")
        return

    def start_console(self):
        """Starts the acquisition controller if one is not already running, otherwise passes
            This behaviour is desirable so that it doesnt need to be initialised every time a script is run which includes a server initialisation"""
        if self.console is None:
            self.console = AcquisitionControl(configuration_file=self.device_config_file)
            self.status = "waiting"
        else:
            print("Console is already running, to restart the console, first kill it, then run the initialisation")
        return
    
    def set_sequence(self, seq_file_path : str):
        if self.console is None:
            print("Handle error if console is not running")
        else:
            self.status = "unrolling"
            self.console.set_sequence(sequence = seq_file_path)
            self.status = "waiting"
        return
    
    def execute_sequence(self, user_path : str, save_unprocessed : bool = False):
        
        self.status = "running"
        
        acq_data : AcquisitionData = self.console.run()
        
        self.status = "waiting"
        
        acq_data.save(save_unprocessed=save_unprocessed, user_path=user_path)
        
        base_path = acq_data.session_path if user_path is None else os.path.join(user_path, "")
        os.makedirs(base_path, exist_ok=True)

        acq_folder = acq_data.meta["folder_name"]
        output_folder = os.path.join(base_path, acq_folder)
        
        return acq_data.raw, output_folder
    
        