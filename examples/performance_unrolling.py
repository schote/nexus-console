"""Performance test (speed) of sequence unrolling with a turbo spin echo sequence (TSE)."""
# %%
# imports
from timeit import timeit

from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.spcm_control.interface_acquisition_parameter import Dimensions
import console.utilities.sequences as sequences

# %load_ext line_profiler

# %%
# Read sequence
provider = SequenceProvider(rf_to_mvolt=0.005, gpa_gain=[4.7, 4.7, 4.7], gradient_efficiency=[0.000451, 0.0004, 0.00037])

# Set maximum amplitude per channel
provider.output_limits = (200, 6000, 6000, 6000)

# Load pulseq sequence
# seq_path = "../sequences/export/tse.seq"
# seq.read(seq_path)

# Construct sequence:
seq, _ = sequences.tse.tse_v1_2d.constructor(
    echo_time=20e-3,
    repetition_time=300e-3,
    etl=1,
    gradient_correction=510e-6,
    rf_duration=200e-6,
    ro_bandwidth=20e3,
    fov=Dimensions(x=220e-3, y=220e-3, z=225e-3),
    n_enc=Dimensions(x=64, y=64, z=0)
)
provider.from_pypulseq(seq)

# %%
# Measure execution time of unrolling

n_calls = 1
call = "provider.unroll_sequence(2.031e6)"
duration = timeit(call, number=n_calls, globals=globals())

print(f"Total rollout duration of {n_calls} calls: {duration} sec")
print(f"Mean sequence rollout duration ({n_calls} calls): {duration/n_calls} sec")


# %%
# Use lineprofiler to analyse unrolling algorithm

# %lprun -s -f seq.unroll_sequence seq.unroll_sequence(2.031e6)

# %%
# Plot
# from console.utilities.plot_unrolled_sequence import plot_unrolled_sequence

# seq_unrolled = provider.unroll_sequence(2.031e6)
# fig, ax = plot_unrolled_sequence(seq_unrolled, seq_range=(0, 640000), output_limits=[200, 6000, 6000, 6000])
# fig.set_figwidth(10)
# fig.set_figheight(12)
# %%
