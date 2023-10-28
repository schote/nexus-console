"""Performance test (speed) of sequence unrolling with a turbo spin echo sequence (TSE)."""
# %%
# imports
from timeit import timeit

from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.spcm_control.interface_acquisition_parameter import Dimensions
import console.utilities.sequences as sequences

%load_ext line_profiler

# %%
# Read sequence
seq = SequenceProvider(rf_to_volt=0.005, grad_to_volt=0.005)

# Set maximum amplitude per channel
seq.output_limits = (200, 6000, 6000, 6000)

# Load pulseq sequence
# seq_path = "../sequences/export/tse.seq"
# seq.read(seq_path)

# Construct sequence:
tse_seq, _ = sequences.tse.tse_v1.constructor(
    etl=7, n_enc=Dimensions(x=70, y=70, z=49)
)
seq.from_pypulseq(tse_seq)

# %%
# Measure execution time of unrolling

# n_calls = 10
# call = "seq.unroll_sequence(2.031e6)"
# duration = timeit(call, number=n_calls, globals=globals())

# print(f"Total rollout duration of {n_calls} calls: {duration} sec")
# print(f"Mean sequence rollout duration ({n_calls} calls): {duration/n_calls} sec")


# %%
# Use lineprofiler to analyse unrolling algorithm

%lprun -s -f seq.unroll_sequence seq.unroll_sequence(2.031e6)

# %%
# result = seq.unroll_sequence(2.031e6)