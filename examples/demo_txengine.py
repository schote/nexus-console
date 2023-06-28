# %%
import os
import yaml
import numpy as np

from console.utilities.io import yaml_loader
from console.spcm_control.tx_device import TxCard

import matplotlib.pyplot as plt

# %%

config_file = os.path.normpath("../device_config.yaml")

# Load config
with open(config_file, 'rb') as file:
    config = yaml.load(file, Loader=yaml_loader)

# Get devices: RxCard or TxCard
devices = config["devices"]
# Get first device in list
tx_card: TxCard = list(filter(lambda device: device.__name__ == "TxCard", devices))[0]

# %%
# Define a sequence
max_val = 15000   # np.iinfo(np.uint16).max
waveform = np.linspace(start=0, stop=max_val, num=4000, dtype=np.int16)
waveform = np.append(waveform, np.array([max_val]*10000, dtype=np.int16))
waveform = np.append(waveform, np.linspace(start=max_val, stop=0, num=4000, dtype=np.int16))
sequence = np.concatenate([waveform, waveform, waveform, waveform])

print(f"Number of waveform sample points: {len(waveform)}") # Calculate sequence sample points
print(f"Memory size of test sequence: {sequence.nbytes}") # Calculate bytes
print(f"Bytes per sample point: {int(sequence.nbytes/len(sequence))}")


plt.plot(sequence)
plt.show()


# %%
# Run experiment
tx_card.connect()

# %%
tx_card.operate(sequence)

# %%
tx_card.disconnect()

# %%
