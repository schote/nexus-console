# %%
from math import pi
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from pypulseq import make_adc, make_delay, make_sinc_pulse, calc_duration, calc_rf_center, make_sinc_pulse, make_trapezoid

from console.utilities.plotly_sequence import get_sequence_plot
import numpy as np

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


# >> Parameters

# RF parameters
rf_duration = 800e-6
rf_bandwidth = 20e3

# Sequence specific timing
te = 20e-3
tr = 500e-3

# Readout/ADC
fov = 250e-3     # 25 cm
n_ro = 256
n_pe = 64

ro_bw = 50e3   # 50 kHz bandwidth
adc_duration = n_ro / ro_bw
# k_width = n_ro / fov
delta_k = 1 / fov

slice_thickness = 3e-3
spoiler_area = 1000


# >> Definition of block events

# 90 degree excitation rf pulse
rf_excitation, grad_slice, grad_slice_re = make_sinc_pulse(
    flip_angle=pi/2,                 # 90 °
    duration=rf_duration,               
    slice_thickness=slice_thickness,    
    system=system,
    apodization=0.4,
    time_bw_product=4,
    return_gz=True
)

# 180 degree refocussing pulse
rf_refocussing = make_sinc_pulse(
    flip_angle=pi,       # 180°
    duration=rf_duration,   # keep duration -> doubles amplitude
    system=system,
    use='refocusing'
)

# Calculate spoiler gradients
grad_spoiler_1 = make_trapezoid(
    channel='z', 
    area=spoiler_area + grad_slice_re.area, 
    system=system
)
grad_spoiler_2 = make_trapezoid(
    channel='z', 
    area=spoiler_area, 
    system=system
)

rf_refocussing.delay = max(calc_duration(grad_spoiler_1), rf_refocussing.delay)

# Define delays
delay_te_1 = te / 2 - (calc_duration(grad_slice) - calc_rf_center(rf_excitation)[0] - rf_excitation.delay) - rf_refocussing.delay - calc_rf_center(rf_refocussing)[0]
delay_te_2 = te / 2 - calc_duration(rf_refocussing) + rf_refocussing.delay + calc_rf_center(rf_refocussing)[0] - adc_duration / 2

# Define readout gradient and prewinder
# z is defined as readout axis (!)
grad_ro = make_trapezoid(
    channel='x', 
    system=system, 
    flat_area=n_ro * delta_k, 
    flat_time=adc_duration
)
grad_ro_pre = make_trapezoid(
    channel='x', 
    system=system, 
    area=grad_ro.area / 2 + delta_k / 2, 
    duration=delay_te_1
)

# Define adc event
adc = make_adc(
    num_samples=n_ro, 
    system=system, 
    duration=adc_duration, 
    delay=delay_te_2
)

grad_ro.delay = delay_te_2 - grad_ro.rise_time
delay_tr = tr - calc_duration(rf_excitation) - delay_te_1 - calc_duration(rf_refocussing)

pe_flat_area = n_pe * (delta_k / 2)
pe_area_values = np.linspace(-1, 1, n_pe) * pe_flat_area

for pe_area in pe_area_values:
    # Define phase encoding gradient
    # Precomputed area, duration equals slice select rephaser
    grad_pe = make_trapezoid(
        channel='y', 
        system=system, 
        area=pe_area, 
        duration=delay_te_1
    )
    
    # Add sequence blocks
    seq.add_block(rf_excitation, grad_slice)
    seq.add_block(grad_ro_pre, grad_pe)
    seq.add_block(rf_refocussing, grad_spoiler_1)
    seq.add_block(adc, grad_ro, grad_spoiler_2, make_delay(delay_tr))

seq.set_definition('Name', 'Cartesian SE')

# %%
# Check sequence timing and plot
ok, e = seq.check_timing()
seq.plot(time_disp='ms') if ok else print(e)


# %% 
# Write sequence
seq.write('./export/se_cartesian.seq')
# %%
