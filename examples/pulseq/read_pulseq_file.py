# %%
# Imports
from pypulseq import Sequence
from pprint import pprint

from console.utilities.sequence_plot import get_sequence_plot

# %%
# Read file
file_path = "./tse.seq"

seq = Sequence()
seq.read(file_path)

# %%
# Plot sequence
# get_sequence_plot(seq)

# %%
# Sequence content
print(f"Number of blocks: {len(seq.block_events)}")

pprint(seq.get_block(1))
# %%
pprint(seq.get_block(50))
pprint(seq.get_block(2))
# %%
