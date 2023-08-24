# %%
# imports
import numpy as np

from console.utilities.io import get_sequence_provider
from console.utilities.line_plots import plot_spcm_data

# %%
# Get sequence provider object and read sequence
seq = get_sequence_provider("../device_config.yaml")
# seq.read("./sequences/fid_proj.seq")
seq.read("./sequences/txrx_test.seq")

# %%
sqnc, gate, total_samples = seq.unroll_sequence()

# Sequence and adc gate are returned as list of numpy arrays => concatenate them
sqnc = np.concatenate(sqnc)
gate = np.concatenate(gate)

# %%
# Combine sequence and gate 
# For int16 (signed!) 15th bit corresponds to -2**15 = -32768
sqnc = sqnc.astype(np.int16)
gate = ((-2**15) * gate).astype(np.int16)

sqnc[1::4] = sqnc[1::4] >> 1 | gate
sqnc[2::4] = sqnc[2::4] >> 1 | gate
sqnc[3::4] = sqnc[3::4] >> 1 | gate

fig = plot_spcm_data(sqnc, contains_gate=True)
fig.show()

# %%