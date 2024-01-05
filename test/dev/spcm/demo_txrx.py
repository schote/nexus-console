"""Demonstraction of transmit and receive devices."""
# %%
# imports
import time

import matplotlib.pyplot as plt
import numpy as np

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from console.utilities.load_config import get_instances

# %%
# Get instances from configuration file
seq, tx_card, rx_card = get_instances("../device_config.yaml")

# Set max amplitude per channel from TX card to unroll sequence directly to int16
seq.max_amp_per_channel = tx_card.max_amplitude

# Read sequence
seq.read("../sequences/export/gradient_test.seq")
#seq.read("../sequences/export/tse.seq")

# Unrolling the sequence...
sqnc: UnrolledSequence = seq.unroll_sequence()

#fig, ax = plot_spcm_data(sqnc, use_time=True)
#fig.show()

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

gateAll = []
n_pulses_display = len(rx_card.rx_data)
for i in range(n_pulses_display):
    gateAll.append(rx_card.rx_data[i])

# Plot all gates make subplots of 4 columns according to the number of gates
fig, ax = plt.subplots(int(np.ceil(n_pulses_display/4)), 4, figsize=(10,3))
for i in range(n_pulses_display):
    ax[i//4, i%4].plot(np.linspace(0,len(rx_card.rx_data[i])/(rx_card.sample_rate*1e6),len(rx_card.rx_data[i]/(rx_card.sample_rate*1e6))),gateAll[i])
    # Hide x labels and tick labels for top plots and y ticks for right plots.
    ax[i//4, i%4].label_outer()
    ax[i//4, i%4].set_xlabel("Time / ms")
    #ax[i//4, i%4].set_ylabel("Amp / V")


# Plot all gates in one plot
plt.show()
# %%
plt.figure()
plt.plot(rx_card.rx_data[9])
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
