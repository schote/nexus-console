# %%
from math import pi
from pypulseq.Sequence.sequence import Sequence
from pypulseq.make_adc import make_adc
from pypulseq.make_block_pulse import make_block_pulse
from pypulseq.opts import Opts

from console.pulseq_interpreter.sequence_provider import SequenceProvider

# %%
# >> Build pulseq sequence
# Define system
system = Opts(
    rf_ringdown_time=100e-6,    # Time delay at the beginning of an RF event
    rf_dead_time=100e-6,        # time delay at the end of RF event
    adc_dead_time=100e-6,       # time delay at the beginning of ADC event
)
seq = Sequence(system)

# Parameters
rf_duration = 100e-6 # 200 us
rf_bandwidth = 20e3 # 20 kHz
rf_flip = pi/2
rf_phase = pi/2

num_samples = 5000
adc_duration = 1e-3 # 4 ms
te = 5e-3

# >> RF rect pulse with varying duration
# 90 degree RF sinc pulse
rf_block_1 = make_block_pulse(
    flip_angle=rf_flip,
    duration=rf_duration,
    phase_offset=rf_phase,
    system=system,
)

# 180 degree RF sinc pulse
rf_block_2 = make_block_pulse(
    flip_angle=rf_flip*2,   # twice the flip angle => 180°
    duration=rf_duration*2, # twice the duration => equal amplitudes
    phase_offset=rf_phase,
    system=system,
)

# ADC event
adc = make_adc(
    num_samples=num_samples,
    duration=adc_duration, 
    system=system, 
    delay=system.adc_dead_time
)

delay_1 = te / 2 - rf_block_1.shape_dur / 2 - rf_block_2.shape_dur / 2
delay_2 = te / 2 - rf_block_2.shape_dur / 2 - adc_duration / 2

# Define sequence
seq.add_block(rf_block_1)
seq.add_block(delay_1)
seq.add_block(rf_block_2)
seq.add_block(delay_2)
seq.add_block(adc)
seq.set_definition('Name', 'se_spectrum')

# %%
# How to construct a provider object with an existing seq object?
# Implementation of a copy constructor?
# def from_pulseq_object(self, seq: Sequence) -> SequenceProvider:
#     provider 
# provider = SequenceProvider(seq) 

# %%
