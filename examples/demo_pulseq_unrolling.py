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
seq.read("../sequences/export/dual-se_spec.seq")
# seq.read("../sequences/export/fid_proj.seq")
# seq.read("../sequences/export/gradient_test.seq")
# seq.read("../sequences/export/tse.seq")

# %%
f_0 = 2.031e6
seq.max_amp_per_channel = [200, 6000, 6000, 6000]
sqnc: UnrolledSequence = seq.unroll_sequence(f_0)

# %%

fig, _ = plot_spcm_data(sqnc, use_time=False)
fig.show()

# %%
# Check reference clock
import numpy as np
import matplotlib.pyplot as plt

seq = np.concatenate(sqnc.seq)
reference_clk = -(seq[3::4] >> 15)

plt.plot(reference_clk[200800:201000])
# %%
