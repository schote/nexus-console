"""Demonstraction of transmit and receive devices."""
# %%
# imports
import time
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from console.utilities.load_config import get_instances
from console.utilities.spcm_data_plot import plot_spcm_data
from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from console.utilities.processing import apply_ddc
from scipy import signal

is_setup = False
# Get instances from configuration file
seq, tx_card, rx_card = get_instances("../device_config.yaml")

# %%
# Connect to tx and rx card
if not is_setup:
    tx_card.connect()
    rx_card.connect()
    is_setup = True




# %%
# Set max amplitude per channel from TX card to unroll sequence directly to int16
seq.max_amp_per_channel = tx_card.max_amplitude

# filename = "se_spectrum_400us_sinc_8ms-te"
# filename = "se_spectrum_400us_sinc_20ms-te"
# filename = "se_spectrum_400us_sinc_30ms-te"
# filename = "se_proj_400us-sinc_20ms-te"
filename = "se_proj_400us_sinc_12ms-te"
# filename = "se_spectrum_200us-rect"

seq.read(f"../sequences/export/{filename}.seq")

# %%
# Unroll and plot the sequence

# f_0 = 2033520   # larmor frequency
# f_0 = 2031536
f_0 = 2031000
# f_0 = 2031146

# seq.rf_to_volt = 0.03     # large phantom, sinc 400us
# seq.rf_to_volt = 0.08     # small phantom, sinc 400us
seq.rf_to_volt = 0.0035

# seq.grad_to_volt = 0.000015
# seq.grad_to_volt = -0.00025
# seq.grad_to_volt = -0.0001
seq.grad_to_volt = 0.0


sqnc: UnrolledSequence = seq.unroll_sequence(f_0, b1_scaling=0.5)
# sqnc.seq[-1][1::4] = sqnc.seq[-1][1::4] * -1

print("Relative RF output max.: ", np.max(np.concatenate(sqnc.seq)[0::4])/np.iinfo(np.int16).max)

fig, ax = plot_spcm_data(sqnc, use_time=True)
fig.show()

# %%
# Start the rx card
rx_card.start_operation()

# Wait 100ms starting the tx sequence
time.sleep(0.1)

tx_card.start_operation(sqnc)

# Wait 2s to finish tx operation
time.sleep(1)

# Stop both cards, use 500ms delay to ensure that everything is captured
tx_card.stop_operation()
rx_card.stop_operation()

# Plot rx signal
rx_data = rx_card.rx_data[0]



# %%
# adc duration
adc_duration = rx_data.size/20e6

filtered = apply_ddc(rx_data, kernel_size=400, f_0=f_0, f_spcm=20e6)
filtered_fft = np.fft.fftshift(np.fft.fft(filtered))
fft_freq = np.fft.fftshift(np.fft.fftfreq(filtered.size, adc_duration/filtered.size))

fig, ax = plt.subplots(1, 2, figsize=(10, 4))
ax[0].plot(rx_data)
ax[1].plot(fft_freq, np.abs(filtered_fft))
ax[1].set_xlim([-10e3, 10e3])

print("Signal max. [a.u.]: ", np.round(np.abs(np.max(filtered_fft)), 2))

f_0_true = np.round(f_0 - fft_freq[np.argmax(np.abs(filtered_fft))])
print("Larmor frequency [Hz]: ", f_0_true)

# t_stamp = datetime.now().strftime('%Y-%m-%d-%H%M')
# np.save(f"data/{t_stamp}_{filename}_{seq.grad_to_volt}-grad-to-volt", rx_data)



# %%
# raw_fft_freq = np.fft.fftshift(np.fft.fftfreq(rx_data.size, 1/20e6))
# raw_fft = np.fft.fftshift(np.fft.fft(rx_data))

# plt.plot(raw_fft_freq, np.abs(raw_fft))
# plt.xlim([f_0-10e3, f_0+10e3])
# # plt.yscale("log")

# dt = 1/(rx_card.sample_rate*1e6)
# time_ax = np.arange(10e3, 10e3+rx_data.size) * dt * 1e3    # time in ms
# freq_ax = np.fft.fftfreq(rx_data.size, d=dt)
# pos_freq = freq_ax > 0
# fft_freq = np.fft.fftshift(np.fft.fftfreq(rx_data.size, rx_data.size))
# rx_data_fft = np.abs(np.fft.fft(rx_data))

# fig, ax = plt.subplots(1, 2, figsize=(12, 5))
# ax[0].plot(time_ax, rx_data)
# ax[1].plot(freq_ax[pos_freq], rx_data_fft[pos_freq])
# ax[1].set_xlim([2.03e6, 2.04e6])
# #ax[1].set_ylim([40, 100])
# ax[0].set_ylabel("Amplitude [mV]")
# ax[1].set_ylabel("Amplitude (dB scale) [a.u.]")
# ax[0].set_xlabel("Time [ms]")
# ax[1].set_xlabel("Frequency [Hz]")


# %%
# Disconnect cards
tx_card.disconnect()
rx_card.disconnect()
is_setup = False
# %%
