"""Spin-Echo imaging sequence from ISMRM live-demo."""
# %%
# imports
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from pypulseq import make_block_pulse, make_delay, calc_duration, make_adc
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
TR = 250e-3
TE = 60e-3

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

# Define delays and ADC events
delay_te_1 = TE/2 - calc_duration(rf_ex)/2 - calc_duration(rf_ref)/2
delay_te_2 = TE/2 - calc_duration(rf_ref) + rf_ref.delay + calc_duration(rf_ref) - adc_duration/2

adc = make_adc(n_x, duration=adc_duration, system=system, delay=delay_te_2)

delay_tr = TR - calc_duration(rf_ex) - delay_te_1 - calc_duration(rf_ref)

assert delay_te_1 >= 0
assert delay_te_2 >= 0
assert delay_tr >= 0

# Loop over repetitions and define sequence blocks
for i in range(n_rep):
    seq.add_block(rf_ex)
    seq.add_block(make_delay(delay_te_1))
    seq.add_block(rf_ref)
    seq.add_block(adc, make_delay(delay_tr))

# Plot the sequence
seq.plot()

#%%
# Check whether the timing of the sequence is compatible with the scanner
ok, error_report = seq.check_timing()

if ok:
    print('Timing check passed successfully')
else:
    print('Timing check failed! Error listing follows:')
    for err in error_report:
        print(err)

# %%
# Write the sequence to a pulseq file
seq.write(f'./export/se_spec_avg-{n_rep}.seq')

# Calculate k-space but only use it to check the TE calculation
# ktraj_adc, ktraj, t_excitation, t_refocusing, t_adc = seq.calculate_kspacePP()

# assert abs(t_refocusing - t_excitation - TE/2) < 1e-6  # Check that the refocusing happens at 1/2 of TE
# assert abs(t_adc[n_x//2] - t_excitation - TE) < adc.dwell  # Check that the echo happens as close as possible to the middle of the ADC element

# %%
