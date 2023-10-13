# %%
from math import pi
from pypulseq.Sequence.sequence import Sequence
from pypulseq.make_adc import make_adc
from pypulseq.make_delay import make_delay
from pypulseq.make_block_pulse import make_block_pulse
from pypulseq.make_sinc_pulse import make_sinc_pulse
from pypulseq.make_trapezoid import make_trapezoid
from pypulseq.opts import Opts

from console.utilities.plotly_sequence import get_sequence_plot

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

# ----- Parameters
# RF parameters
rf_duration = 100e-6 # 200 us
rf_bandwidth = 20e3 # 20 kHz
rf_flip = pi/2
rf_phase = pi/2

# Sequence specific timing
te = 10e-3

# Readout/ADC
ro_bw = 50e3   # 50 kHz bandwidth
num_samples = 256
adc_dwell_time = 1 / ro_bw
adc_duration = adc_dwell_time * num_samples
fov = 0.255     # 25.5 cm
k_width = num_samples / fov
rise_time = 200e-6



# >> Definition of block events
# 90 degree RF block pulse
rf_block_90 = make_block_pulse(
    flip_angle=rf_flip,
    duration=rf_duration,
    phase_offset=rf_phase,
    system=system,
)

rf_block_180 = make_block_pulse(
    flip_angle=rf_flip*2,   # twice the flip angle => 180°
    duration=rf_duration,   # keep duration -> doubles amplitude
    phase_offset=rf_phase,
    system=system,
)

# Calculate readout gradient:
# delta_kx = gamma * Gx * delta_t_RO
# => Gx = delta_kx / (gamma * delta_t_RO), 
# with delta_kx = 1 / FOV, we obtain
# Gx = 1 / (gamma * FOV * delta_t_RO)
# delta_t_RO = 1 / BW
# Gx = BW / (gamma * FOV)
gr_ro = make_trapezoid(
    channel="x",
    system=system,
    flat_area=k_width,
    flat_time=adc_duration,
    rise_time=rise_time
)



# Calculate 

# ADC event
adc = make_adc(
    num_samples=num_samples,
    duration=adc_duration, 
    system=system, 
    delay=rise_time
)

# Define delays
delay_1 = make_delay(te / 2 - rf_block_90.shape_dur / 2 - rf_block_180.shape_dur / 2)
delay_2 = make_delay(te / 2 - rf_block_180.shape_dur / 2 - adc_duration / 2)


# >> Define sequence
seq.add_block(rf_block_90)
seq.add_block(delay_1)
seq.add_block(rf_block_180)
seq.add_block(delay_2)
seq.add_block(gr_ro, adc)

seq.set_definition('Name', 'se_projection_block-pulse')


# %%
# Check sequence timing and plot
ok, e = seq.check_timing()
seq.plot(time_range=(0, 100e-3), time_disp='us') if ok else print(e)


# %% 
# Write sequence
seq.write('./export/se_projection_block-pulse.seq')
# %%
