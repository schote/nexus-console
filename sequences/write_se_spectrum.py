# %%
from math import pi
import pypulseq as pp

# %%
# Define system
system = pp.Opts(
    rf_ringdown_time=100e-6,    # Time delay at the beginning of an RF event
    rf_dead_time=100e-6,        # time delay at the end of RF event
    adc_dead_time=200e-6,       # time delay at the beginning of ADC event
)
seq = pp.Sequence(system)

# Parameters
# rf_duration = 400e-6
rf_duration = 250e-6
num_samples = 5000
adc_duration = 4e-3 # 4 ms
te = 20e-3
# te = 12e-3

# >> RF sinc pulse with varying amplitudes

## 90 degree RF sinc pulse
# rf_90 = pp.make_sinc_pulse(
#     flip_angle=pi/2,
#     system=system,
#     duration=rf_duration,
#     apodization=0.5,
#     # phase_offset=pi/2,
# )

# # 180 degree RF sinc pulse
# rf_180 = pp.make_sinc_pulse(
#     flip_angle=pi,   # twice the flip angle => 180°
#     system=system,
#     duration=rf_duration,
#     apodization=0.5,
#     # phase_offset=pi/2,
# )


# >> RF rect pulse 
# 90 degree
rf_90 = pp.make_block_pulse(
    flip_angle=pi/2,
    duration=rf_duration,
    # phase_offset=pi/2,
    system=system,
)

# 180 degree with two times the duration
rf_180 = pp.make_block_pulse(
    flip_angle=pi,              # twice the flip angle => 180°
    duration=rf_duration*2,     # twice the duration => equal amplitudes
    # phase_offset=pi/2,
    system=system,
)

# ADC event
adc = pp.make_adc(
    num_samples=num_samples,
    duration=adc_duration, 
    system=system
)

delay_1 = pp.make_delay(te / 2 - pp.calc_duration(rf_90) / 2 - pp.calc_duration(rf_180) / 2)
delay_2 = pp.make_delay(te / 2 - pp.calc_duration(rf_180) / 2 - adc_duration / 2)

# Define sequence
seq.add_block(rf_90)
seq.add_block(delay_1)
seq.add_block(rf_180)
seq.add_block(delay_2)
seq.add_block(adc)

# Add another echo
# seq.add_block(delay_2)
# seq.add_block(rf_180)
# seq.add_block(delay_2)
# seq.add_block(adc)

seq.set_definition('Name', 'Spin echo spectrum sequence')


# Check sequence timing and plot
# ok, e = seq.check_timing()
# seq.plot(time_range=(0, 1e-3), time_disp='ms') if ok else print(e)
seq.plot()


# %% 
# Write sequence
# seq.write('./export/se_spectrum_100us.seq')
seq.write(f'./export/se_spectrum_2500us_sinc_{int(te*1e3)}ms-te.seq')
# %%
