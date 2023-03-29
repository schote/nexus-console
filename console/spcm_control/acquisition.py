import yaml
from pprint import pprint

from console.spcm_control.pyspcm import *
from console.spcm_control.spcm_tools import *
from console.spcm_control.device import SpectrumDevice, yaml_loader


class AcquisitionControl:
    
    def __init__(self, config_path: str = os.path.join(os.path.dirname(__file__), 'device_config.yaml')):
        
        with open(config_path, 'rb') as file:
            config = yaml.load(file, Loader=yaml_loader)
        
        self.devices: SpectrumDevice = config['spcm_cards']
        
        for dev in self.devices:
            pprint(dev.dict())
            
            
    def init_cards(self):
        pass
    
    def write_sequence(self):
        pass
        
