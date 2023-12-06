"""Read and plot unrolled pulseq files with sequence provider class."""
# %%
# imports
from console.utilities.load_config import get_instances

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
import console.utilities.sequences as sequences
from console.utilities.sequences import Dimensions

# %%
# Get sequence provider object and read sequence
sqnc_provider, _, _ = get_instances("../../device_config.yaml")

# Read sequence file
# seq.read("../sequences/export/dual-se_spec.seq")
# seq.read("../sequences/export/fid_proj.seq")
# seq.read("../sequences/export/gradient_test.seq")
# seq.read("../sequences/export/tse_low-field.seq")
# seq.read("../sequences/export/se_proj_400us_sinc_12ms-te.seq")
# seq.read("../../sequences/export/se_cartesian_64-pe.seq")

seq, traj = sequences.tse.tse_2d.constructor(
    echo_time=20e-3,
    repetition_time=100e-3,
    etl=1,
    gradient_correction=510e-6,
    rf_duration=200e-6,
    ro_bandwidth=20e3,
    fov=Dimensions(x=220e-3, y=220e-3, z=225e-3),
    n_enc=Dimensions(x=64, y=64, z=0)
)

sqnc_provider.from_pypulseq(seq)

# %%
f_0 = 2.031e6
sqnc: UnrolledSequence = sqnc_provider.unroll_sequence(f_0)

# %%
# Plot sequence
fig, ax = sqnc_provider.plot_unrolled(time_range=[100e-3, 200e-3])

# %%
