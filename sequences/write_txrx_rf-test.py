# %%
from math import pi
from pypulseq.Sequence.sequence import Sequence
from pypulseq.make_adc import make_adc
from pypulseq.make_sinc_pulse import make_sinc_pulse
from pypulseq.opts import Opts

# Todo fix plotting 
# from console.utilities.sequence_plot import get_sequence_plot

# %%

# f0 = 2.048e6 # approx 2 MHz
# gyro = 42.577478518 * 1e6 # Hz/T

# Define system
system = Opts(
    rf_ringdown_time=100e-6,    # Time delay at the beginning of an RF event
    rf_dead_time=100e-6,        # time delay at the end of RF an event
    rf_raster_time=1e-7,
)

seq = Sequence(system)

# Parameters
rf_duration = 200e-6
rf_bandwidth = 20e3 # 20 kHz
rf_flip_angle = pi/2
rf_phase = pi/2
rf_delay = 100e-6

adc_duration = rf_duration + system.rf_dead_time + system.rf_ringdown_time


# 90 degree RF sinc pulse
rf_block = make_sinc_pulse(
    flip_angle=rf_flip_angle,
    system=system,
    duration=rf_duration,
    apodization=0.5,
    phase_offset=rf_phase,
    return_gz=False,
)

adc = make_adc(
    num_samples=1000,
    duration=adc_duration, 
    system=system, 
)

# Define sequence
seq.add_block(adc, rf_block)
seq.set_definition('Name', 'txrx_test')


# %%
# Check sequence timing and plot

#fig = get_sequence_plot(seq)
#fig.show()

# seq.plot(time_range=(0, 1e-3), time_disp='ms')
# ok, e = seq.check_timing()
# seq.plot(time_range=(0, 1e-3), time_disp='us') if ok else print(e)


# %% 
# Write sequence
seq.write('txrx_test.seq')
# %%
