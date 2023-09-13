"""Demonstraction of transmit and receive devices."""
# %%
# imports
import time

import matplotlib.pyplot as plt
from console.utilities.load_config import get_instances
from console.utilities.spcm_data_plot import plot_spcm_data
from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence

# %%
# Get instances from configuration file
seq, tx_card, rx_card = get_instances("../device_config.yaml")

# Set max amplitude per channel from TX card to unroll sequence directly to int16
seq.max_amp_per_channel = tx_card.max_amplitude

# Read sequence
seq.read("../sequences/export/gradient_test.seq")

# Unrolling the sequence...
sqnc: UnrolledSequence = seq.unroll_sequence(return_as_int16=True)

fig, ax = plot_spcm_data(sqnc, use_time=True)
fig.show()

# %%
# Connect to tx and rx card
tx_card.connect()
rx_card.connect()

# Start the rx card
rx_card.start_operation()

# Wait 1s starting the tx sequence
time.sleep(1)

tx_card.start_operation(sqnc)

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
gate3 = rx_card.rx_data[2]
gate4 = rx_card.rx_data[3]
gate5 = rx_card.rx_data[4]
gate6 = rx_card.rx_data[5]
gate7 = rx_card.rx_data[6]
gate8 = rx_card.rx_data[7]

# TODO : Automate this
fig, ax = plt.subplots(2, 4, figsize=(10,3))
ax[0,0].plot(gate1)
ax[0,1].plot(gate2)
ax[0,2].plot(gate3)
ax[0,3].plot(gate4)
ax[1,0].plot(gate5)
ax[1,1].plot(gate6)
ax[1,2].plot(gate7)
ax[1,3].plot(gate8)
plt.show()
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

# %%
