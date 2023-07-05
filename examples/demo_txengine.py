# %%
import os
import yaml
import numpy as np

from console.utilities.io import yaml_loader
from console.spcm_control.tx_device import TxCard

import matplotlib.pyplot as plt

# %%
# Define configuration file
config_file = os.path.normpath("../device_config.yaml")

# Load config
with open(config_file, 'rb') as file:
    config = yaml.load(file, Loader=yaml_loader)

# Get devices: RxCard or TxCard, take first card in list
devices = config["devices"]
tx_card: TxCard = list(filter(lambda device: device.__name__ == "TxCard", devices))[0]

# %%
# Definition of trapezoid waveforms with different amplitudes
# Base trapezoid 
max_val = 1
# waveform = np.linspace(start=0, stop=max_val, num=4000)
# waveform = np.append(waveform, np.array([max_val]*10000))
# waveform = np.append(waveform, np.linspace(start=max_val, stop=0, num=4000))
waveform = np.linspace(start=0, stop=max_val, num=100000)
waveform = np.append(waveform, np.array([max_val]*400000))
waveform = np.append(waveform, np.linspace(start=max_val, stop=0, num=100000))
n_samples = len(waveform)

# Scaling of base trapezoid
sequence = np.empty(shape=(4, n_samples), dtype=np.int16)
for k, amp in enumerate([400, 600, 800, 1000]):
    sequence[k, :] = waveform * tx_card.output_to_card_value(value=amp, channel=k)
    
# Flatten sequence in Fortran order:
# [[ch0_0, ch0_1, ...], [ch0_0, ch0_1, ...], ..., [ch0_0, ch0_1, ...]]
# => [ch0_0, ch1_0, ch2_0, ch3_0, ch0_1, ch1_1, ..., ch0_N, ch1_N, ch2_N, ch3_N]]
sequence = sequence.flatten(order="F")

print(f"Number of sample points per channel: {n_samples}") # Calculate sequence sample points
print(f"Memory size of test sequence: {sequence.nbytes}") # Calculate bytes
print(f"Bytes per sample point: {int(sequence.nbytes/len(sequence))}")

# Plot trapezoid waveforms, amplitude in int16 values
fig, ax = plt.subplots(1, 1)
ax.plot(sequence[0::4])
ax.plot(sequence[1::4])
ax.plot(sequence[2::4])
ax.plot(sequence[3::4])
plt.show()


# %%
# Run experiment
tx_card.connect()

# %%
tx_card.operate(sequence)

# %%
tx_card.disconnect()

# %%
