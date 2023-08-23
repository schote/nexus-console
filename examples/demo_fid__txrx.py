# %%
# imports
import os
import time

import matplotlib.pyplot as plt
import numpy as np
from console.utilities.io import (RxCard, SequenceProvider, TxCard,
                                  get_rx_card, get_sequence_provider,
                                  get_tx_card)
from console.utilities.line_plots import plot_spcm_data

# %%
# Get sequence provider object and read sequence
seq: SequenceProvider = get_sequence_provider("../device_config.yaml")
seq.read("./pulseq/fid_proj.seq")

# %%
# Unrolling the sequence...
sqnc, gate, total_samples = seq.unroll_sequence()

# Sequence and adc gate are returned as list of numpy arrays => concatenate them
sqnc = np.concatenate(sqnc)
gate = np.concatenate(gate)
# %%
tx_card: TxCard = get_tx_card("../device_config.yaml")
rx_card: RxCard = get_rx_card("../device_config.yaml")

# %%
data = tx_card.prepare_sequence(sqnc, gate)
fig = plot_spcm_data(data, contains_gate=True)
fig.show()

# %%
# Connect to tx card
tx_card.connect()

# %%
# Connect to rx card
rx_card.connect()

# %%
rx_card.start_operation()
# %%
for i in range (10):
    tx_card.start_operation(data)
    time.sleep(3)
    tx_card.stop_operation()
# %%
rx_card.stop_operation()

# %%
# Disconnect cards
tx_card.disconnect()
rx_card.disconnect()


# %%
# Plot rx data
rx_file = "./rx_channel_4_2.npy"
file_exists = False
while not file_exists:
    file_exists = os.path.exists(rx_file)

rx_data = np.load(rx_file)

# %%
sample_rate = 1/10e6
time_points = np.arange(len(rx_data)) * sample_rate
#to_idx = 140000

fig, ax = plt.subplots(1, 1, figsize=(10, 4))
#ax.plot(time_points[:to_idx]*1e3, np.abs(rx_data[:to_idx]))
ax.plot(time_points*1e3, np.abs(rx_data))
ax.set_ylabel("RX amplitude")
ax.set_xlabel("Time [ms]")
# %%
