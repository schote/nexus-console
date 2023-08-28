# %%
import os
import yaml
import numpy as np

from console.utilities.spcm_data_plot import plot_spcm_data
from console.utilities.load_config import Loader
#from console.spcm_control.tx_device import TxCard
from console.spcm_control.rx_device import RxCard

#Added for buffer stuff
from console.spcm_control.spcm.pyspcm import *  # noqa # pylint: disable=unused-wildcard-import
# %%
# Define configuration file
config_file = os.path.normpath("../device_config.yaml")

# Load config
with open(config_file, 'rb') as file:
    config = yaml.load(file, Loader=Loader)

# Get devices: RxCard or TxCard, take first card in list
devices = config["devices"]
rx_card: RxCard = list(filter(lambda device: device.__name__ == "RxCard", devices))[0]
# %%
rx_card.connect()

# %%
rx_card.operate()


rx_card.disconnect()
# %%
