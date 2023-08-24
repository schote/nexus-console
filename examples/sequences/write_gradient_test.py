# %%
from pypulseq.Sequence.sequence import Sequence
from pypulseq.make_adc import make_adc
from pypulseq.make_extended_trapezoid import make_extended_trapezoid
from pypulseq.make_delay import make_delay
from pypulseq.opts import Opts
import numpy as np

from console.utilities.sequence_plot import get_sequence_plot

# %%
seq = Sequence()

# Parameters
num_samples = 1000
adc_duration = 4e-3
amp1 = 50000
amp2 = 100000
amp3 = 150000
amp4 = 200000
flat_time = 400e-6
rise_time = 200e-6


# ADC event
# TODO: Add dead time at the beginning? Currently ADC starts at 1/2 of gradient rise time
# => Add 1/2 of gradient rise time
adc = make_adc(
    num_samples=num_samples,
    duration=adc_duration, 
)

g1_t = np.array([
    0, 
    rise_time, # rise 1
    rise_time+flat_time, # flat 1
    2*rise_time+flat_time, # rise 2
    2*rise_time+2*flat_time, # flat 2
    3*rise_time+2*flat_time, # rise 3
    3*rise_time+5*flat_time, # flat top
    4*rise_time+5*flat_time, # fall 3
    4*rise_time+6*flat_time, # flat 2
    5*rise_time+6*flat_time, # fall 2
    5*rise_time+7*flat_time, # flat 1
    6*rise_time+7*flat_time, # fall 1
])
g1_amps = np.array([0, amp1, amp1, amp2, amp2, amp3, amp3, amp2, amp2, amp1, amp1, 0])
g1 = make_extended_trapezoid(channel="x", times=g1_t, amplitudes=g1_amps)


g2_t = np.array([
    0,
    2*rise_time,
    2*rise_time+2*flat_time,
    4*rise_time+2*flat_time,
    4*rise_time+6*flat_time,
    8*rise_time+6*flat_time
])
g2_amps = np.array([0, amp2, amp2, amp4, amp4, 0])
g2 = make_extended_trapezoid(channel="x", times=g2_t, amplitudes=g2_amps)

# Define sequence
seq.add_block(g1, adc)
seq.add_block(make_delay(2e-3))
seq.add_block(g2, adc)
seq.set_definition('Name', 'gradient_test')

# %%
# Check sequence timing and plot

# fig = get_sequence_plot(seq)
# fig.show()

seq.plot(time_disp='ms')
# ok, e = seq.check_timing()
# seq.plot(time_range=(0, 1e-3), time_disp='us') if ok else print(e)

# %% 
# Write sequence
seq.write('grad_test.seq')
# %%
