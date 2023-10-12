"""Demonstraction of transmit and receive devices."""
# %%
# imports
import sys
import time
import numpy as np
import matplotlib.pyplot as plt
from console.utilities.load_config import get_instances
from console.utilities.spcm_data_plot import plot_spcm_data
from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence

testname = sys.argv[1]
# %%
# Get instances from configuration file
seq, tx_card, rx_card = get_instances("../device_config.yaml")

# Set max amplitude per channel from TX card to unroll sequence directly to int16
seq.max_amp_per_channel = tx_card.max_amplitude
# seq.read("../sequences/export/se_spectrum.seq")
seq.read("../sequences/export/adc.seq")
# Unroll and plot the sequence
sqnc: UnrolledSequence = seq.unroll_sequence(2023456) #2.023e6

fig, ax = plot_spcm_data(sqnc, use_time=True)
fig.show()

# %%
# Connect to tx and rx card
tx_card.connect()
rx_card.connect()
# %%
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




# %%
# Plot rx signal


amplitude = rx_card.rx_data[0]
# Let's create a time array
# Sampling rate is 10 MHz. 
sampling_rate = 20e6
time_ = np.arange(0, len(amplitude), 1)

# Convert the time to seconds
time_ = time_/sampling_rate
#plot the data
plt.figure()
plt.plot(time_,rx_card.rx_data[0])
plt.savefig(f'/home/sileme01/temp_jan/{testname}_time.svg')


# Now take the FFT of the data
fft_data = np.fft.fft(amplitude)
print('fft_data.shape = ', fft_data.shape)
freq = np.fft.fftfreq(len(fft_data), d=1/sampling_rate)
db_fft_data = 20*np.log10(np.abs(fft_data))

# Get only the positive frequencies
positive_freq = freq > 0
freq = freq[positive_freq] / 1e6
db_fft_data = db_fft_data[positive_freq]


# Now plot the FFT data
plt.figure()
plt.plot(freq,db_fft_data)
# limit the frequency range to 2.0 MHz to 2.1 MHz
#plt.xlim([2.0160, 2.0170])
plt.xlim([2.0, 2.05])
plt.savefig(f'/home/sileme01/temp_jan/{testname}_spectrum.svg')
np.save(f'/home/sileme01/temp_jan/{testname}.npy', amplitude)

# %%

# %%
# Disconnect cards
tx_card.disconnect()
rx_card.disconnect()
plt.show()
# %%
