# %%
# imports
from console.pulseq_interpreter.sequence import SequenceProvider
import os
import time

# %%
# Read sequence
seq = SequenceProvider()
seq_path = os.path.normpath("/Users/schote01/code/spectrum-pulseq/console/pulseq_interpreter/seq/fid.seq")
seq.read("./pulseq/tse.seq")

# %%
t0 = time.time()
unrolled_sequence, total_samples = seq.unroll_sequence()
t_execution = time.time() - t0

print(f"Sequence unrolling: {t_execution} s")