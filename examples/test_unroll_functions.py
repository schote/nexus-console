# %%
# imports
from console.pulseq_interpreter.sequence import SequenceProvider
import os
import numpy as np
from pprint import pprint
import plotly.express as px 
import pandas as pd
import time

# %%
# Read sequence
seq = SequenceProvider()
seq_path = os.path.normpath("/Users/schote01/code/spectrum-pulseq/console/pulseq_interpreter/seq/fid.seq")
seq.read("./pulseq/tse.seq")


# %% 
# Get longest rf event from sequence
# t0 = time.time()

# rf_list = []
# for k in seq.block_events.keys():
#     if (b := seq.get_block(k)).rf:
#         rf_list.append(b.rf.shape_dur)
        
# # rf_dur_max = max(rf_list, key=attrgetter('shape_dur')).shape_dur
# rf_dur_max = max(rf_list)

# t_execution = time.time() - t0
# print(f"Calculation of longest RF event: {t_execution} s")
# print(f"Longest RF duration: {rf_dur_max}")

# %%
# # Precalculate carrier signal
# t0 = time.time()
# seq.precalculate_carrier()
# t_execution = time.time() - t0
# print(f"Precalculation of carrier signal: {t_execution} s")


# # Test RF calculation
# block = seq.get_block(2)    # block 2 contains rf
# n_samples = int(block.block_duration/seq.spcm_sample_rate)

# print("Test rf block:")
# pprint(block.rf)

# # Calculate RF waveform
# rf = seq.calculate_rf(rf_block=block.rf, num_total_samples=n_samples)

# # Plot RF event
# fig = px.line(pd.DataFrame({
#     "time (ms)": list(np.arange(n_samples)*seq.spcm_sample_rate*1e3),
#     "amplitude": rf
# }), x="time (ms)", y="amplitude", title="RF")
# fig.show()

# %%
# PROBLEM (?)
# Mismatch of block duration and rf durations ? => fill the rest with zeros
# total_rf_duration = block.rf.shape_dur + block.rf.delay + block.rf.dead_time + block.rf.ringdown_time
# block_duration = block.block_duration

# print(f"Total RF duration: {total_rf_duration}\nBlock duration: {block_duration}")
# print("RF samples: ", len(rf))
# print("Block samples: ", n_samples)

# %%
# Test arbitrary gradient unrolling event

block = seq.get_block(1)    # block 1 contains arbitrary gradient
n_samples = int(block.block_duration / seq.spcm_sample_rate)

gradient_arbitrary = seq.calculate_gradient(block.gz, n_samples)

pprint(block.gz)

fig = px.line(pd.DataFrame({
    "time (ms)": list(np.arange(n_samples)*seq.spcm_sample_rate*1e3),
    "amplitude": gradient_arbitrary
}), x="time (ms)", y="amplitude", title="Arbitrary Gradient")
fig.show()


# %%
# Test trapezoidal gradient unrolling event

block = seq.get_block(3)    # block 3 contains trapezoidal gradient
n_samples = int(block.block_duration / seq.spcm_sample_rate)

gradient_trapezoidal = seq.calculate_gradient(block.gx, n_samples)

pprint(block.gx)

fig = px.line(pd.DataFrame({
    "time (ms)": list(np.arange(n_samples)*seq.spcm_sample_rate*1e3),
    "amplitude": gradient_trapezoidal
}), x="time (ms)", y="amplitude", title="Trapezoidal Gradient")
fig.show()
# %%
