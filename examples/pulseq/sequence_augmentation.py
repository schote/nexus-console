# %%
# Imports
from pypulseq import Sequence
from pprint import pprint

from console.utilities.sequence_plot import get_sequence_plot

# %%
# Read file
file_path = r"./tse.seq"

seq = Sequence()
seq.read(file_path)

# %%
# Plot sequence
fig = get_sequence_plot(seq)
fig.write_html(f"./tse_plot.html")
fig.show()

# %%
# Sequence content
duration, num_blocks, num_events = seq.duration()
print(f"Number of blocks: {num_blocks}, number of events: {num_events}, sequence duration: {duration} s")

print("Block example:")
pprint(seq.get_block(1))

# %%
# Extract event examples
for k in range(1, num_blocks+1):
    block = seq.get_block(k)
    if (rf := block.rf):
        print("RF Event:")
        pprint(rf)
        break

for k in range(1, num_blocks+1):
    block = seq.get_block(k)
    if (gradient := block.gx) and block.gx.type == "grad":
        print("Gradient Event:")
        pprint(gradient)
        break
    
for k in range(1, num_blocks+1):
    block = seq.get_block(k)
    if (gradient := block.gx) and block.gx.type == "trap":
        print("Trapez gradient Event:")
        pprint(gradient)
        break

for k in range(1, num_blocks+1):
    block = seq.get_block(k)
    if (adc := block.adc):
        print("ADC Event:")
        pprint(adc)
        break
# %%
