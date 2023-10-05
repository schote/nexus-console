# %%
from math import pi
from pypulseq.Sequence.sequence import Sequence
from pypulseq.make_adc import make_adc
from pypulseq.make_block_pulse import make_block_pulse
from pypulseq.make_sinc_pulse import make_sinc_pulse
from pypulseq.opts import Opts

# %%

# f0 = 2.048e6 # approx 2 MHz
# gyro = 42.577478518 * 1e6 # Hz/T

# Define system
system = Opts(
    rf_ringdown_time=100e-6,    # Time delay at the beginning of an RF event
    rf_dead_time=200e-6,        # time delay at the end of RF event
    adc_dead_time=100e-6,       # time delay at the beginning of ADC event
)

seq = Sequence(system)

# Parameters
rf_duration = 100e-6 # 100 us
rf_bandwidth = 20e3 # 20 kHz
rf_flip_angle = pi/2
rf_phase = pi/2

num_samples = 5e3
adc_duration = 1e-3 # 4 ms


# 90 degree RF sinc pulse
# rf_block = make_sinc_pulse(
#     flip_angle=rf_flip_angle,
#     system=system,
#     duration=rf_duration,
#     slice_thickness=10,
#     apodization=0.5,
#     time_bw_product=4,
#     phase_offset=rf_phase,
#     return_gz=False,
# )

# 90 degree RF block pulse
rf_block = make_block_pulse(
    flip_angle=rf_flip_angle, 
    duration=rf_duration, 
    bandwidth=rf_bandwidth, 
    use='excitation', 
    system=system
)

# ADC event
adc = make_adc(
    num_samples=num_samples,
    duration=adc_duration, 
    system=system, 
    delay=system.adc_dead_time
)

# Define sequence
seq.add_block(rf_block)
seq.add_block(adc)
seq.set_definition('Name', 'fid')


# %%
# Check sequence timing and plot

seq.plot(time_disp='us')
# ok, e = seq.check_timing()
# seq.plot(time_range=(0, 1e-3), time_disp='us') if ok else print(e)


# %% 
# Write sequence
# seq.write('./export/fid.seq')