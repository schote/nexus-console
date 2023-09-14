"""Read and plot unrolled pulseq files with sequence provider class."""
# %%
# imports
from console.utilities.load_config import get_instances
from console.utilities.spcm_data_plot import plot_spcm_data

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence

# %%
# Get sequence provider object and read sequence
seq, _, _ = get_instances("../device_config.yaml")

# Read sequence file
seq.read("../sequences/export/fid_proj.seq")
# seq.read("../sequences/export/gradient_test.seq")
# seq.read("../sequences/export/tse.seq")

# %%
seq.max_amp_per_channel = [1000, 1000, 1000, 1000]
sqnc: UnrolledSequence = seq.unroll_sequence()

# %%

fig, _ = plot_spcm_data(sqnc, seq_range=(5, 20e3), use_time=False)
fig.show()

# %%