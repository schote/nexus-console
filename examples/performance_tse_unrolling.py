"""Performance test (speed) of sequence unrolling with a turbo spin echo sequence (TSE)."""
# %%
# imports
import time

from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.spcm_data_plot import plot_spcm_data

# %%
# Read sequence
seq = SequenceProvider(rf_to_volt=0.2, grad_to_volt=0.001)

# This is optional: If channel maxima are not set, we cannot return sequence as int16 directly
seq.max_amp_per_channel = (1000, 1000, 1000, 1000)

# Load pulseq sequence
seq_path = "../sequences/export/tse.seq"
seq.read(seq_path)

# %%
# Time unrolling with return_as_int equals False
t0 = time.time()
seq_unrolled = seq.unroll_sequence(return_as_int16=False)
t_execution = time.time() - t0

print(f"Sequence unrolling to float: {t_execution} s")

# %%
# Time unrolling with return_as_int equals True

# TODO: ATM unrolling the sequence to int16 takes approx. twice as long as unrolling it to float.
# >> This is probably due to the fact, that unrolling is performed to float first and casted to int16
# >> in an additional step. Instead, we could try to calculate the unrolled sequence directly in int16
# >> datatype (casting gradient amplitudes before resampling for instance). This would also save memory.

t0 = time.time()
seq_unrolled = seq.unroll_sequence(return_as_int16=True)
t_execution = time.time() - t0

print(f"Sequence unrolling to int16: {t_execution} s")

# %%
# Plot result
fig, ax = plot_spcm_data(seq_unrolled, use_time=True)
fig.show()

# %%
