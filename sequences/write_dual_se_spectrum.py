# %%
from math import pi
from pypulseq.Sequence.sequence import Sequence
from pypulseq.make_adc import make_adc
from pypulseq.make_block_pulse import make_block_pulse
from pypulseq.make_sinc_pulse import make_sinc_pulse
from pypulseq.make_delay import make_delay
from pypulseq.opts import Opts

# %%

# f0 = 2.048e6 # approx 2 MHz
# gyro = 42.577478518 * 1e6 # Hz/T

# Define system
system = Opts(
    rf_ringdown_time=100e-6,    # Time delay at the beginning of an RF event
    rf_dead_time=100e-6,        # time delay at the end of RF event
    adc_dead_time=200e-6,       # time delay at the beginning of ADC event
)
seq = Sequence(system)

# Parameters
rf_duration = 400e-6 # 200 us
rf_bandwidth = 20e3 # 20 kHz
rf_flip = pi/2
rf_phase = pi/2

num_samples = 256
ro_bw = 50e3
adc_duration = num_samples / ro_bw
te = 12e-3  # 12 ms

# >> RF sinc pulse with varying duration
# 90 degree RF sinc pulse
rf_block_1 = make_sinc_pulse(
    flip_angle=rf_flip,
    duration=rf_duration,
    apodization=0.5,
    phase_offset=rf_phase,
    system=system,
)

# 180 degree RF sinc pulse
rf_block_2 = make_sinc_pulse(
    flip_angle=rf_flip*2,   # twice the flip angle => 180°
    duration=rf_duration, # twice the duration => equal amplitudes
    apodization=0.5,
    phase_offset=rf_phase,
    system=system,
)

# ADC event
adc = make_adc(
    num_samples=num_samples,
    duration=adc_duration, 
    system=system
)

# Make delays
delay_1 = make_delay(te / 2 - rf_block_1.shape_dur / 2 - rf_block_2.shape_dur / 2)
delay_2 = make_delay(te / 2 - rf_block_2.shape_dur / 2 - adc_duration / 2)

# Define sequence
seq.add_block(rf_block_1)
seq.add_block(delay_1)
seq.add_block(rf_block_2)
seq.add_block(delay_2)
seq.add_block(adc)  # first readout
seq.add_block(delay_2)
seq.add_block(rf_block_2)
seq.add_block(delay_2)
seq.add_block(adc)  # second redout
seq.set_definition('Name', 'Dual Spin-Echo Spectrum')


# %%
# Check sequence timing and plot
ok, e = seq.check_timing()
seq.plot(time_disp='ms') if ok else print(e)


# %% 
# Write sequence
seq.write(f'./export/dual-se_spec.seq')
# %%
