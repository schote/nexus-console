# %%
from pypulseq.Sequence.sequence import Sequence
from pypulseq.make_adc import make_adc
from pypulseq.make_extended_trapezoid import make_extended_trapezoid
from pypulseq.make_delay import make_delay
import numpy as np

#from console.utilities.sequence_plot import get_sequence_plot

# %%
seq = Sequence()

# Parameters
num_samples = 1000
adc_duration = 4e-3
# Note. adc_duration2 must be equal to adc_duration otherwise does not work
adc_duration2 = 4e-3
amp1 = 50000
amp2 = 100000
amp3 = 150000
amp4 = 200000
flat_time = 400e-6
rise_time = 200e-6

adc = make_adc(num_samples=num_samples, duration=adc_duration)
adc2 = make_adc(num_samples=num_samples, duration=adc_duration2)

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


g3_t = np.array([
    0,
    2*rise_time,
    2*rise_time+2*flat_time,
    4*rise_time+2*flat_time,
    4*rise_time+6*flat_time,
    8*rise_time+6*flat_time
])
g3_amps = np.array([0, amp4, amp4, amp2, amp2, 0])
g3 = make_extended_trapezoid(channel="x", times=g3_t, amplitudes=g3_amps)

# Define sequence
seq.add_block(g1, adc)
seq.add_block(make_delay(8e-3))
seq.add_block(g2, adc)
seq.add_block(make_delay(8e-3))
seq.add_block(g3, adc2)
seq.add_block(make_delay(8e-3))
seq.add_block(g2, adc)
seq.add_block(make_delay(8e-3))
seq.add_block(g1, adc)
seq.add_block(make_delay(8e-3))
seq.add_block(g2, adc)
seq.add_block(make_delay(8e-3))
seq.add_block(g1, adc)
seq.add_block(make_delay(8e-3))
seq.add_block(g3, adc)
seq.add_block(make_delay(8e-3))

for i in range (0, 16):
    seq.add_block(g1, adc)
    seq.add_block(make_delay(8e-3))

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
seq.write('./export/gradient_test.seq')
# %%
