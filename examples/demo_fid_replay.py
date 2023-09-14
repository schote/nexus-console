"""Replay demonstration of FID sequence with projection gradient."""
# %%
# imports
import time

from console.utilities.load_config import get_instances
from console.utilities.spcm_data_plot import plot_spcm_data
from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence

# %%
# Get sequence provider object and read sequence
provider, tx_card, _ = get_instances("../device_config.yaml")

provider.max_amp_per_channel = tx_card.max_amplitude
provider.read("../sequences/export/fid_proj.seq")

# %%
# Unroll and plot the sequence
t0 = time.time()
sqnc: UnrolledSequence = provider.unroll_sequence()
t_execution = time.time() - t0

print(f"Sequence unrolling: {t_execution} s")

fig, ax = plot_spcm_data(sqnc, use_time=True)
fig.show()

# %%
# Connect to card and replay sequence
tx_card.connect()
time.sleep(1)
tx_card.start_operation(sqnc)
time.sleep(3)
tx_card.stop_operation()
tx_card.disconnect()
# %%


# Get sequence provider and tx device instances
provider, tx_card, _ = get_instances("../device_config.yaml")

# Max. amplitudes of TX card channels need to be set at sequence provider.
# This ensures correct amplitude scaling of the pulseq sequence.
provider.max_amp_per_channel = tx_card.max_amplitude
provider.read("../sequences/export/fid_proj.seq")

# Unroll and plot the sequence
sqnc: UnrolledSequence = provider.unroll_sequence(return_as_int16=True)

# Plot the sequence
fig, ax = plot_spcm_data(sqnc, use_time=True)
fig.show()

# Replay the sequence
tx_card.connect()
time.sleep(1)
tx_card.start_operation(sqnc)
time.sleep(3)
tx_card.stop_operation()
tx_card.disconnect()