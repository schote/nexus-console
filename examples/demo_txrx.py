# %%
# imports
import os
import time

import matplotlib.pyplot as plt
import numpy as np
from console.utilities.load_config import get_instances
from console.utilities.spcm_data_plot import plot_spcm_data

# %%
# Get instances from configuration file
seq, tx_card, rx_card = get_instances("../device_config.yaml")

# Read sequence
seq.read("../sequences/export/gradient_test.seq")

# Unrolling the sequence...
sqnc, gate, total_samples = seq.unroll_sequence()

# Sequence and adc gate are returned as list of numpy arrays => concatenate them
sqnc = np.concatenate(sqnc)
gate = np.concatenate(gate)

data = tx_card.prepare_sequence(sqnc, gate)
fig = plot_spcm_data(data, contains_gate=True)
fig.show()

# %%
# Connect to tx and rx card
tx_card.connect()
rx_card.connect()

# Start the rx card
rx_card.start_operation()

# Wait 1s starting the tx sequence
time.sleep(1)

tx_card.start_operation(data)

# Wait 3s to finish tx operation
time.sleep(3)

# Stop both cards, use 500ms delay to ensure that everything is captured
tx_card.stop_operation()
time.sleep(1)
rx_card.stop_operation()

# Disconnect cards
tx_card.disconnect()
rx_card.disconnect()


# %%

# TODO: Plot acquired data
gate1 = rx_card.rx_data[0]
gate2 = rx_card.rx_data[1]

fig, ax = plt.subplots(1, 2, figsize=(10,3))
ax[0].plot(gate1)
ax[1].plot(gate2)

# %%
# # Plot rx data
# # rx_file = "./rx_20230824-141639.npy"
# rx_file = "./rx_20230904-233221.npy"

# file_exists = False
# while not file_exists:
#     file_exists = os.path.exists(rx_file)
# rx_data = np.load(rx_file)


# sample_rate = 1/10e6
# time_points = np.arange(len(rx_data)) * sample_rate
# #to_idx = int(8e-3/sample_rate)

# fig, ax = plt.subplots(1, 1, figsize=(10, 4))
# ax.plot(time_points*1e3, np.abs(rx_data))
# # ax.plot(time_points*1e3, np.abs(rx_data))
# ax.set_ylabel("RX amplitude")
# ax.set_xlabel("Time [ms]")
