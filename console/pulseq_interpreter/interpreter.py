# %%
import pypulseq as pp
import numpy as np


# %%
# Read sequence
seq = pp.Sequence()
seq.read("./seq/tse_pypulseq.seq")

# Read sequence blocks as dict
blocks = seq.dict_block_events
# Print specific block from sequence object
print(seq.get_block(1))

# %%
