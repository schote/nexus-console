"""Read and plot unrolled pulseq files with sequence provider class."""
# %%
# imports
import console.utilities.sequences as sequences
from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import SequenceProvider

# %%
# Get sequence provider object and read sequence
provider = SequenceProvider(rf_to_mvolt=0.005, gpa_gain=[1.0, 1.0, 1.0], gradient_efficiency=[0.4e-3, 0.4e-3, 0.4e-3], output_limits=[200, 6000, 6000, 6000])

# Read sequence file
# provider.read("../sequences/export/dual-se_spec.seq")
# provider.read("../sequences/export/fid_proj.seq")
# provider.read("../sequences/export/gradient_test.seq")
# provider.read("../sequences/export/tse_low-field.seq")
# provider.read("../sequences/export/se_proj_400us_sinc_12ms-te.seq")
# provider.read("../sequences/export/se_cartesian_64-pe.seq")

# seq = sequences.se_spectrum.constructor(
#     echo_time=20e-3,
#     rf_duration=200e-6,
#     use_sinc=False
# )
seq = sequences.se_spectrum_dl.constructor()
provider.from_pypulseq(seq)

# %%
f_0 = 2.031e6
sqnc: UnrolledSequence = provider.unroll_sequence(f_0)

# %%
provider.plot_unrolled(time_range=[0, -1])

# %%
