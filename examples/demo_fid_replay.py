# %%
# imports
import time

import numpy as np

from console.utilities.io import get_sequence_provider, SequenceProvider
from console.utilities.io import get_tx_card, TxCard
from console.utilities.line_plots import plot_spcm_data


# %%
# Get sequence provider object and read sequence
seq: SequenceProvider = get_sequence_provider("../device_config.yaml")
seq.read("./pulseq/fid_proj.seq")

# %%
t0 = time.time()
sqnc, gate, total_samples = seq.unroll_sequence()
t_execution = time.time() - t0

# Sequence and adc gate are returned as list of numpy arrays => concatenate them
sqnc = np.concatenate(sqnc)
gate = np.concatenate(gate)

print(f"Sequence unrolling: {t_execution} s")
print(f"Total number of sampling points (per channel): {total_samples}")
# %%
# Combine sequence and gate 
# For int16 (signed!) 15th bit corresponds to -2**15 = -32768
_sqnc = sqnc.astype(np.int16)
_gate = ((-2**15) * gate).astype(np.int16)

_sqnc[1::4] = _sqnc[1::4] >> 1 | _gate
_sqnc[2::4] = _sqnc[2::4] >> 1 | _gate
_sqnc[3::4] = _sqnc[3::4] >> 1 | _gate

fig = plot_spcm_data(_sqnc, contains_gate=True)
fig.show()

# %%
# tx_card: TxCard = get_tx_card("../device_config.yaml")

# %%
# Connect to card and replay sequence
# TODO: Test this...

# tx_card.connect()
# tx_card.start_operation(sqnc, gate)
# time.sleep(3)
# get_tx_card.stop_operation()
# tx_card.disconnect()