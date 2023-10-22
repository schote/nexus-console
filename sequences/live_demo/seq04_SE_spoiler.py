"""Spin-Echo imaging sequence from ISMRM live-demo."""
# %%
# imports
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from pypulseq import make_block_pulse, make_delay, calc_duration, make_adc, make_trapezoid, calc_rf_center
from math import pi

# %%
# Create system object with specified parameters
system = Opts(
    rf_ringdown_time=20e-6,
    rf_dead_time=100e-6,
    adc_dead_time=20e-6
)

# Create a new sequence object
seq = Sequence(system)

n_x = 4096
n_rep = 10
adc_duration = 51.2e-3
rf_duration = 1000e-6
tr = 250e-3
te = 60e-3
spoiler_area = 1000  # Spoiler area in 1/m (=Hz/m*s)

# Create non-selective excitation and refocusing pulses
rf_ex = make_block_pulse(
    flip_angle=pi/2,
    duration=rf_duration,
    system=system
)

rf_ref = make_block_pulse(
    flip_angle=pi,
    duration=rf_duration,
    system=system,
    use='refocusing'
)
# Calculate spoiler gradient, let's put it on X axis for now
g_sp = make_trapezoid(channel='x', area=spoiler_area, system=system)
rf_ref.delay = max(calc_duration(g_sp), rf_ref.delay)

# Define delays and ADC events
delay_te_1 = te/2 - (
    calc_duration(rf_ex) - calc_rf_center(rf_ex)[0] - rf_ex.delay
) - rf_ref.delay - calc_rf_center(rf_ref)[0]

delay_te_2 = te/2 - calc_duration(rf_ref) + rf_ref.delay + calc_rf_center(rf_ref)[0] - adc_duration/2

assert delay_te_2 > calc_duration(g_sp)

adc = make_adc(n_x, duration=adc_duration, system=system, delay=delay_te_2)


delay_tr = tr - calc_duration(rf_ex) - delay_te_1 - calc_duration(rf_ref) if n_rep > 1 else 0

assert delay_te_1 >= 0
assert delay_te_2 >= 0
assert delay_tr >= 0

# Loop over repetitions and define sequence blocks
for i in range(n_rep):
    seq.add_block(rf_ex)
    seq.add_block(make_delay(delay_te_1))
    seq.add_block(rf_ref, g_sp)
    seq.add_block(adc, g_sp, make_delay(delay_tr))

# Plot the sequence
seq.plot()

# %%
# Check whether the timing of the sequence is compatible with the scanner
ok, error_report = seq.check_timing()

if ok:
    print('Timing check passed successfully')
else:
    print('Timing check failed! Error listing follows:')
    for err in error_report:
        print(err)

# Write the sequence to a pulseq file
seq.write(f'./export/se_spec_spoiler_avg-{n_rep}.seq')

# %%
