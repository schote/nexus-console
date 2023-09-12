# %%
# imports
from console.utilities.load_config import get_instances
from console.utilities.spcm_data_plot import plot_spcm_data

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence

# %%
# Get sequence provider object and read sequence
seq, _, _ = get_instances("../device_config.yaml")
# seq.read("./sequences/fid_proj.seq")
seq.read("../sequences/export/gradient_test.seq")
# seq.read("../sequences/export/tse.seq")

# %%
seq.set_channel_maxima = [1000, 1000, 1000, 1000]
sqnc: UnrolledSequence = seq.unroll_sequence(return_as_int16=False)

# Sequence and adc gate are returned as list of numpy arrays => concatenate them
# sqnc = np.concatenate(sqnc)
# gate = np.concatenate(gate)

# %%

fig, _ = plot_spcm_data(sqnc)
fig.show()

# %%