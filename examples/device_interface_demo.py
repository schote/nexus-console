# %%
# imports
import os
import yaml
from pprint import pprint

from console.spcm_control.device import yaml_loader

# %%
# Load device configuration
# Config file path
config_file = os.path.normpath("/Users/schote01/code/spectrum-pulseq/device_config.yaml")

# Load config
with open(config_file, 'rb') as file:
    config = yaml.load(file, Loader=yaml_loader)

# Get devices: RxCard or TxCard
devices = config["devices"]

# Print devices
for dev in devices:
    print(dev.__name__)
    pprint(dev.dict())
    
    
# %%
# Get the tx card by filtering the class names and call it's init function
tx_card = list(filter(lambda device: device.__name__ == "TxCard", devices))[0]

tx_card.init_card()

# %%
