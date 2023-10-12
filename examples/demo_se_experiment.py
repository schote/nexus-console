"""Demonstraction of transmit and receive devices."""
# %%
# imports
import time
import numpy as np
import matplotlib.pyplot as plt
from console.utilities.load_config import get_instances
from console.utilities.spcm_data_plot import plot_spcm_data
from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence

from scipy import signal

# %%
# Get instances from configuration file
seq, tx_card, rx_card = get_instances("../device_config.yaml")
is_setup = False

# Set max amplitude per channel from TX card to unroll sequence directly to int16
seq.max_amp_per_channel = tx_card.max_amplitude
seq.read("../sequences/export/se_spectrum.seq")

# %%
# Unroll and plot the sequence

f_0 = 2.031e6   # larmor frequency

seq.rf_to_volt = 0.02    #0.005
sqnc: UnrolledSequence = seq.unroll_sequence(f_0)

print("Relative RF output max.: ", np.max(np.concatenate(sqnc.seq)[0::4])/np.iinfo(np.int16).max)

fig, ax = plot_spcm_data(sqnc, use_time=True)
fig.show()
# %%
# Connect to tx and rx card
if not is_setup:
    tx_card.connect()
    rx_card.connect()
    is_setup = True

# %%
# Start the rx card
rx_card.start_operation()

# Wait 1s starting the tx sequence
time.sleep(1)

tx_card.start_operation(sqnc)

# Wait 2s to finish tx operation
time.sleep(2)

# Stop both cards, use 500ms delay to ensure that everything is captured
tx_card.stop_operation()
time.sleep(1)
rx_card.stop_operation()

# %%
# Plot rx signal
rx_data = rx_card.rx_data[0][10000:30000]

rx_data_fft = np.abs(np.fft.fft(rx_data))
rx_data_fft_db = 20 * np.log10(np.abs(rx_data_fft))

dt = 1/(rx_card.sample_rate*1e6)
time_ax = np.arange(10e3, 10e3+rx_data.size) * dt * 1e3    # time in ms
freq_ax = np.fft.fftfreq(rx_data.size, d=dt)
pos_freq = freq_ax > 0

fig, ax = plt.subplots(1, 2, figsize=(12, 5))
ax[0].plot(time_ax, rx_data)
ax[1].plot(freq_ax[pos_freq], rx_data_fft_db[pos_freq])
ax[1].set_xlim([1.95e6, 2.1e6])
ax[1].set_ylim([40, 100])
ax[0].set_ylabel("Amplitude [mV]")
ax[1].set_ylabel("Amplitude (dB scale) [a.u.]")
ax[0].set_xlabel("Time [ms]")
ax[1].set_xlabel("Frequency [Hz]")

# ax[1].set_ylim([0, ])

# %%
# Disconnect cards
tx_card.disconnect()
rx_card.disconnect()
# %%
