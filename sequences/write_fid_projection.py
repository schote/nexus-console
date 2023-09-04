# %%
from math import pi
from pypulseq.Sequence.sequence import Sequence
from pypulseq.make_adc import make_adc
from pypulseq.make_block_pulse import make_block_pulse
from pypulseq.make_sinc_pulse import make_sinc_pulse
from pypulseq.make_trapezoid import make_trapezoid
from pypulseq.opts import Opts

from console.utilities.sequence_plot import get_sequence_plot

# %%

# f0 = 2.048e6 # approx 2 MHz
# gyro = 42.577478518 * 1e6 # Hz/T

# Define system
system = Opts(
    rf_ringdown_time=100e-6,    # Time delay at the beginning of an RF event
    rf_dead_time=100e-6,        # time delay at the end of RF event
    # adc_dead_time=100e-6,       # time delay at the beginning of ADC event
)

seq = Sequence(system)

# Parameters
rf_duration = 0.2e-3 # 200 us
rf_bandwidth = 20e3 # 20 kHz
rf_flip_angle = pi/2
rf_phase = pi/2
ro_bw = 50e3   # 20 kHz bandwidth
num_samples = 1e3
adc_dwell_time = 1 / ro_bw
adc_duration = adc_dwell_time * num_samples
fov = 0.255     # 25.5 cm


# 90 degree RF sinc pulse
rf_block = make_sinc_pulse(
    flip_angle=rf_flip_angle,
    system=system,
    duration=rf_duration,
    slice_thickness=10,
    apodization=0.5,
    time_bw_product=4,
    phase_offset=rf_phase,
    return_gz=False,
)

# # 90 degree RF block pulse
# rf_block = make_block_pulse(
#     flip_angle=rf_flip_angle, 
#     duration=rf_duration, 
#     bandwidth=rf_bandwidth, 
#     use='excitation', 
#     system=system
# )

# Calculate readout gradient:
# delta_kx = gamma * Gx * delta_t_RO
# => Gx = delta_kx / (gamma * delta_t_RO), 
# with delta_kx = 1 / FOV, we obtain
# Gx = 1 / (gamma * FOV * delta_t_RO)
# delta_t_RO = 1 / BW
# Gx = BW / (gamma * FOV)

k_width = num_samples / fov
rise_time = 200e-6

gr_ro = make_trapezoid(
    channel="x",
    system=system,
    flat_area=k_width,
    flat_time=adc_duration,
    rise_time=rise_time
)

# ADC event
# TODO: Add dead time at the beginning? Currently ADC starts at 1/2 of gradient rise time
# => Add 1/2 of gradient rise time
adc = make_adc(
    num_samples=num_samples,
    duration=adc_duration, 
    system=system, 
    delay=rise_time
)

# Define sequence
seq.add_block(rf_block)
seq.add_block(gr_ro, adc)
seq.set_definition('Name', 'fid')


# %%
# Check sequence timing and plot

fig = get_sequence_plot(seq)
fig.show()

# seq.plot(time_range=(0, 1e-3), time_disp='ms')
# ok, e = seq.check_timing()
# seq.plot(time_range=(0, 1e-3), time_disp='us') if ok else print(e)


# %% 
# Write sequence
seq.write('./export/fid_proj.seq')
# %%
