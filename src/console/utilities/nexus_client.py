"""Initial testing on nexus-client."""
import requests
import ipaddress
import logging
import logging.config
import os
import base64
import numpy as np
from datetime import datetime
from pathlib import Path

LOG_LEVELS = [
    logging.DEBUG,
    logging.INFO,
    logging.WARNING,
    logging.ERROR,
    logging.CRITICAL,
]


class NexusClient:
    """ Nexus client class
    
    Main purpose of the class is to interface with the nexus server.
    """
    
    def __init__(
        self,
        server_ip : str = "127.0.0.1", #defaults to local ip and standard port number
        server_port: int = 8000,     
    ):
        try:
           ipaddress.ip_address(server_ip) #check if ip address is valid
        except ValueError as e:
            raise ValueError(f"Invalid IP address {e}.")
        if server_port > 0 and server_port < 2**16:
            # Check to see if the server port number is a valid number
            self.server_URL = f"http://{server_ip}:{server_port}"
            print("Server URL: %s"%(self.server_URL))
        else:
            raise ValueError(f"Invalid port number: {server_port}")
        
        return
    
    def start_nexus_console(self, user_path: str = None):
        # server_status = requests.get(f"{self.server_URL}/nexus-status/").json()
        if user_path is None:
            response = requests.put(f"{self.server_URL}/nexus-console/", json = {})
        else:
            response = requests.put(f"{self.server_URL}/nexus-console/", json = {"path":user_path})
        return response
    
    def set_sequence(self, seq , temp_data_path : str = None):
        # Save the seq file locally and then stream it to the server.
        
        if temp_data_path is None:
            # Create session path (contains all acquisitions of one day), copied from AcqController, uses the same local path
            nexus_data_dir      = os.path.join(Path.home(), "nexus-console")
            session_folder_name = datetime.now().strftime("%Y-%m-%d")
            self.temp_folder    = os.path.join(nexus_data_dir, session_folder_name, "-session/Temp")
            os.makedirs(self.temp_folder, exist_ok=True)
        else:
            if not os.path.exists(temp_data_path):
                os.makedirs(temp_data_path)
            self.temp_folder = os.path.normpath(temp_data_path)
        
        # store pulseq sequence in temporary folder
        seq_file_loc = os.path.join(self.temp_folder, 'sequence-client.seq')
        seq.write(seq_file_loc)
        

        with open(seq_file_loc, "rb") as f:
            response = requests.post(
                f"{self.server_URL}/sequence/",
                files={"seq_file": f}
            )
        return response
    
    def run_sequence(self, output_folder: str, return_data = False, save_unprocessed = False):
        """ Run the currently loaded sequence on the console
        
        
        Returns:
            np.ndarray if return_data = True
        
        """
   
        data_settings = {"return_data":return_data,
                         "save_unprocessed":save_unprocessed,
                         "output_folder":output_folder}
        
        response = requests.post(f"{self.server_URL}/run-sequence/", json = data_settings)
        
        if response.status_code != 200:
            #handle error
            print("Unsuccessful data transfer")
            print(f"Status code: {response.status_code}")
            return response
        
        response_data   = response.json()
        if return_data:
            response_data   = response.json()
            array_shape     = tuple(response_data["data_shape"][0])
            print(array_shape)
            if len(response_data["data"])> 1: 
                scan_data   = np.frombuffer(base64.b64decode(response_data["data"]), dtype = complex).reshape(array_shape)
                return scan_data
            else:
                # Handle missing data
                print("No data transmitted from console")
        return 

    def get_status(self):
        server_status = requests.get(f"{self.server_URL}/nexus-status/", timeout=3)
        return server_status.json()
    
    def get_parameter(self, console_param : str = ""):
        if console_param is None or console_param == "":
            #expect to return dict with all parameters
            param_dict = requests.get(f"{self.server_URL}/parameter/", json = {"name":"", "value":None})
            return param_dict.json()
        else:
            param_data = requests.get(f"{self.server_URL}/parameter/", json = {"name":console_param, "value":None})
            return param_data.json()["value"]
        
    def set_parameter(self, console_param : str, value):
        if isinstance(value, (float, int, str, list, tuple)):
            param_data = requests.post(f"{self.server_URL}/parameter/", json = {"name":console_param, "value":value})
        return param_data.json()

            
