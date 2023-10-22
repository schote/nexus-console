"""Performance test (speed) of sequence unrolling with a turbo spin echo sequence (TSE)."""
# %%
# imports
import time
from timeit import timeit

from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.spcm_data_plot import plot_spcm_data

# %load_ext line_profiler

# %%
# Read sequence
seq = SequenceProvider(rf_to_volt=0.005, grad_to_volt=0.0001)

# Set maximum amplitude per channel
seq.max_amp_per_channel = (200, 6000, 6000, 6000)

# Load pulseq sequence
seq_path = "../sequences/export/tse.seq"
seq.read(seq_path)

# %%
# Measure execution time of unrolling

n_calls = 100
call = "seq.unroll_sequence(2.031e6)"
duration = timeit(call, number=n_calls, globals=globals())

print(f"Total rollout duration of {n_calls} calls: {duration} sec")
print(f"Mean sequence rollout duration ({n_calls} calls): {duration/n_calls} sec")


# %%
# Use lineprofiler to analyse unrolling algorithm

# %lprun -f seq.unroll_sequence seq.unroll_sequence(2.031e6)
