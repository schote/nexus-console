# %%
# imports
import numpy as np
from pypulseq import make_sinc_pulse, make_adc, make_block_pulse, make_delay, make_trapezoid, calc_duration, calc_rf_center, rotate
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence

# %%
# Create system object with specified parameters
system = Opts(
    rf_ringdown_time=20e-6,
    rf_dead_time=100e-6,
    adc_dead_time=20e-6
)

# Create a new sequence object
seq = Sequence(system)

# Define sequence parameters
adc_duration = 5.12e-3 / 2
rf_duration1 = 3e-3
rf_duration2 = 1e-3
TR = 225e-3
TE = 60e-3
spA = 1000

slice_thickness = 3e-3
fov = 250e-3
Nx = 256
Nr = 256
Ndummy = 10
delta = 2 * np.pi / Nr

# Create 90 degree slice selection pulse and gradient
rf_ex, gs, gsr = make_sinc_pulse(
    flip_angle=np.pi/2,
    system=system,
    duration=rf_duration1,
    slice_thickness=slice_thickness,
    apodization=0.4,
    time_bw_product=4,
    return_gz=True
)
gs.channel = 'x'  # Change to X for sagittal orientation

# Create non-selective refocusing pulse
rf_ref = make_block_pulse(
    flip_angle=np.pi,
    duration=rf_duration2,
    system=system,
    use='refocusing'
)

# Calculate spoiler gradients
g_sp1 = make_trapezoid(
    channel='x', 
    area=spA + gsr.area, 
    system=system
)
rf_ref.delay = max(calc_duration(g_sp1), rf_ref.delay)

g_sp2 = make_trapezoid('x', area=spA, system=system)

# Define delays and ADC events
delay_te1 = TE / 2 - (calc_duration(gs) - calc_rf_center(rf_ex)[0] - rf_ex.delay) - rf_ref.delay - calc_rf_center(rf_ref)[0]
delay_te2 = TE / 2 - calc_duration(rf_ref) + rf_ref.delay + calc_rf_center(rf_ref)[0] - adc_duration / 2

deltak = 1 / fov
gr = make_trapezoid(
    channel='z', 
    system=system, 
    flat_area=Nx * deltak, 
    flat_time=adc_duration
)
adc = make_adc(
    num_samples=Nx, 
    system=system, 
    duration=adc_duration, 
    delay=delay_te2
)
gr.delay = delay_te2 - gr.rise_time

gr_pre = make_trapezoid(
    channel='z', 
    system=system, 
    area=gr.area / 2 + deltak / 2, 
    duration=delay_te1
)

delay_tr = TR - calc_duration(rf_ex) - delay_te1 - calc_duration(rf_ref)

# Loop over repetitions and define sequence blocks
for i in range(1 - Ndummy, Nr + 1):
    seq.add_block(rf_ex, gs)
    seq.add_block(*rotate(gr_pre, axis='x', angle=delta * (i - 1)))
    seq.add_block(rf_ref, g_sp1)
    if i > 0:
        seq.add_block(*rotate(adc, gr, g_sp2, make_delay(delay_tr), axis='x', angle=delta * (i - 1)))
    else:
        seq.add_block(*rotate(gr, g_sp2, make_delay(delay_tr), axis='x', angle=delta * (i - 1)))

# Plot the sequence
seq.plot()

# Check whether the timing of the sequence is compatible with the scanner
ok, error_report = seq.check_timing()

if ok:
    print('Timing check passed successfully')
else:
    print('Timing check failed! Error listing follows:')
    for err in error_report:
        print(err)

# Set sequence definitions for FOV and Name
seq.set_definition('fov', [slice_thickness * 16, fov, fov])
seq.set_definition('name', 'se_rad')

seq.plot()

# %%
# Write the sequence to a pulseq file
seq.write('./export/se_radial.seq')

# %%
