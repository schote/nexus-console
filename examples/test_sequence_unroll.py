# %%
# imports
from console.pulseq_interpreter.sequence_provider import SequenceProvider
import os
import time
import numpy as np
from console.utilities.line_plots import plot_spcm_data

# %%
# Read sequence
seq = SequenceProvider(rf_double_precision=False)
seq_path = os.path.normpath("/Users/schote01/code/spectrum-pulseq/console/pulseq_interpreter/seq/fid.seq")
seq.read("./pulseq/tse.seq")

# %%
t0 = time.time()
unrolled_sequence, total_samples = seq.unroll_sequence()
t_execution = time.time() - t0

print(f"Sequence unrolling: {t_execution} s")
print(f"Total number of sampling points (per channel): {total_samples}")
# %%

seq_arr = np.concatenate(unrolled_sequence)

fig = plot_spcm_data(seq_arr[160000000:177000000], num_channels=4)
fig.show()

# %%
