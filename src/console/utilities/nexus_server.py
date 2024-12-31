from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import Union
import uvicorn
from nexus_console_interface import NexusConsoleInterface
import argparse
import os
import numpy as np
import base64

""" Used to launch the nexus server and provide the API interface to the console
    This should only be used to provide the API interface and check the variables passed to the API
    The interface between the API server and the console is handled in nexus_console_interface"""

app = FastAPI()


class PathRequest(BaseModel):
    path: str = None
    #should validate if path is a valid path i.e. is creatable
    
class ParameterRequest(BaseModel):
    name : str
    value : Union[bool, int, float, None] #None is used for get parameter where no value is set in the request
    
class ExperimentRequest(BaseModel):
    name : str
    
class DataHandlingSettings(BaseModel):
    return_data : bool
    save_unprocessed : bool
    output_folder : str
    
def main():
    parser = argparse.ArgumentParser(description="Run a FastAPI server.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host") # 127.0.0.1 accessible on network, 0.0.0.0 only on local PC
    parser.add_argument("--port", type=int, default=8000, help="Server port")        # Standard port for fastAPI
    parser.add_argument("--folder", type=str, default="", help="User path")
    parser.add_argument("--device_config", type=str, default="spectrum-console-experiments/device_config_lumc.yaml", help="Path to device config")

    args = parser.parse_args()
    
    global nexus 
    nexus = NexusConsoleInterface(device_config_file=args.device_config)


    uvicorn.run(app, host=args.host, port=args.port)
    
    
@app.get("/nexus-config/")
def read_nexus_config() -> str:
    """Return a string containing the path to the yaml device config file.

    Returns
    -------
        str: path to YAML device config file.
    """
    return nexus.device_config_file

@app.post("/nexus-config/")
def set_nexus_config(device_config_yaml : str) -> None:
    """Set the location for the yaml file containing the device config, this can be used to overwrite the default.

    Returns:
        str: stored path to YAML device config file.
    """
    nexus.device_config_file = device_config_yaml
    return nexus.device_config_file

@app.get("/parameter/")
def get_parameter(parameter : ParameterRequest):
    """Return the value of a parameter, or a dictionary containing all console parameters
    Returns:
        if no parameter defined, returns dict of all parameters
        otherwise 
    """
    if parameter.name == "":
        return nexus.get_parameter()
    else:
        param = nexus.get_parameter(param = parameter.name)
        param_name = parameter.name
        parameter_descriptor = {"name":param_name,
                            "value":param}
        return parameter_descriptor

@ app.post("/parameter/")
def set_parameter(parameter : ParameterRequest):
    """Set console parameter
    
    TODO: Input validation
    
    Returns: 
        Value of parameter.
    """
    nexus.set_parameter(parameter.name, parameter.value)
    
    param = nexus.get_parameter(param = parameter.name)
    param_name = parameter.name
    parameter_descriptor = {"name":param_name,
                        "value":param}
    
    return parameter_descriptor
    
    
    
@app.get("/nexus-status/")
def get_nexus_status()-> str:
    """Get the current status of the nexus console
    
    Returns:
        Status message
    """
    return nexus.status

@app.put("/nexus-console/")
# def init_nexus_console(user_path : PathRequest, device_config_yaml : PathRequest = None, console_log_level = logging.DEBUG, file_log_level=logging.DEBUG) -> str:
def init_nexus_console(user_path : PathRequest):
    """ Initialise the acquistion controller
    
    Returns:
        Status message and user path
    """

    nexus.start_console()

    if user_path is None:
        #if no user_path is provided, grab standard path from the console.
        nexus.user_path = nexus.console.session_path
    else:
        # Should check if a valid path is supplied
        if not os.path.exists(user_path.path):
            nexus.user_path = os.makedirs(user_path.path)
        else:
            nexus.user_path = os.path.normpath(user_path.path)
        
    status = {"user_path":str(nexus.user_path),
              "status":nexus.status}
    
    return status

@app.delete("/nexus-console/")
def delete_nexus_console():
    """Kills the currently running instance of the nexus console
    TODO:   Ensure this is handled properly, it seems some data remains in buffer which
            causes issues when starting a new instance of the server and running a sequence
    
    Returns:
        Status message
    """
    nexus.console = None
    nexus.status = "inactive"  
    return {"status":nexus.status}

@app.post("/sequence/")
def set_sequence( seq_file:UploadFile = File(...)):
    """Receive a .seq file from the client, write it to disk and then unroll it if the nexus console is runnning
    TODO: Allow sequence unrolling to happen asynchronously

    Returns:
        confirmation message
    """
    storage_path = os.path.join(nexus.user_path, "temp") # Store sequence in subfolder of session path
    # Check if storage path exists, if not, create it
    if not os.path.exists(storage_path):
        os.makedirs(storage_path)
        
    nexus.storage_path = os.path.normpath(storage_path)
    nexus.pulseq_file_path  = os.path.join(nexus.storage_path, seq_file.filename)
    
    with open(nexus.pulseq_file_path, "wb") as f:
        f.write(seq_file.file.read())
    
    if os.path.isfile(nexus.pulseq_file_path):
        nexus.set_sequence(seq_file_path=nexus.pulseq_file_path)
        return  {"message": f" .seq file written to: {nexus.pulseq_file_path}"}
    else:
        return {"message": f"Error writing pulse file to {nexus.pulseq_file_path}"}
    
@app.get("/sequence/")
def get_sequence():
    """ Return the currently loaded pulseq file
    TODO: Return pulseq file itself
    
    Return:
        str : Dictionary containing location of pulseq file
    """
    try:
        return {"file_location":nexus.pulseq_file_path}
    except AttributeError:
        print("No pulseq file loaded")
        raise HTTPException(status_code=404, detail="No sequence loaded")
        
@app.post("/run-sequence/")
def run_sequence(data_settings : DataHandlingSettings):
    """ Execute the loaded pulse sequence.
        Data is stored locally but can be returned too. Data is returned as a byte string for efficient data transfer
        Reconstructed to complex numpy array on the client side.
        
    TODO: perform checks to see if console is running and a sequence is loaded, handle if not
    TODO: Allow sequence execution to run asynchronously
    
    Return:
        dict
    """
    acq_data, output_folder =  nexus.execute_sequence(user_path = data_settings.output_folder, save_unprocessed = data_settings.save_unprocessed)
   
    data = {"message":"Scan complete",
            "output_folder":output_folder}
    if data_settings.return_data:
        data["data_shape"]   = list(np.shape(acq_data)),
        data["data"]    = base64.b64encode(acq_data.tobytes()).decode("utf-8") #send scan data as a byte string
    return data

# Use argparse for CLI arguments
if __name__ == "__main__":
    main()
    
    