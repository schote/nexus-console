"""Demonstraction of transmit and receive devices."""
# %%
# imports
import time
import numpy as np
import matplotlib.pyplot as plt
from console.utilities.load_config import get_instances
from console.utilities.spcm_data_plot import plot_spcm_data
from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence

# %%
# Get instances from configuration file
seq, tx_card, rx_card = get_instances("../device_config.yaml")

# Set max amplitude per channel from TX card to unroll sequence directly to int16
seq.max_amp_per_channel = tx_card.max_amplitude
seq.read("../sequences/export/se_spectrum.seq")

# Unroll and plot the sequence
sqnc: UnrolledSequence = seq.unroll_sequence(2.02e6)

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
# Plot rx signal
plt.figure()
plt.plot(rx_card.rx_data[0])
# %%
