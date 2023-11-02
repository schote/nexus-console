# %%
from math import pi
import pypulseq as pp
import numpy as np
from console.spcm_control.interface_acquisition_parameter import Dimensions

# %%

# f0 = 2.048e6 # approx 2 MHz
# gyro = 42.577478518 * 1e6 # Hz/T

# Define system
system = pp.Opts(
    rf_ringdown_time=100e-6,    # Time delay at the beginning of an RF event
    rf_dead_time=100e-6,        # time delay at the end of RF event
    adc_dead_time=200e-6,       # time delay at the beginning of ADC event
)

def constructor(
    fov: Dimensions = Dimensions(x=0.22, y=0.22, z=0.),
    n_enc: Dimensions = Dimensions(x=64, y=64, z=0),
    slice_thickness: float = 5e-3,
    slice_select: bool = True,
    readout_bandwidth: float = 20e3,
    echo_time: float = 10e-3,
    repetition_time: float = 300e-3,
)

seq = pp.Sequence(system)


# >> Parameters

# RF
rf_duration = 800e-6
rf_bandwidth = 20e3

# Timing
# Echo time
te = 10e-3
# Repetition time 
tr = 300e-3

# k-Space
# 25 cm field of view
fov = 250e-3
# 256 readout sample points
n_ro = 256
# 64 phase encoding steps
n_pe = 64
# Set slice thickness to 5 mm (?)
slice_thickness = 5e-3
slice_select = True
# Readout bandwidth, used to calculate adc duration
ro_bw = 50e3   # 50 kHz bandwidth
adc_duration = n_ro / ro_bw
delta_k = 1 / fov


# >> Definition of block events
# 90 degree excitation rf pulse
rf_excitation, grad_slice, grad_slice_re = pp.make_sinc_pulse(
    flip_angle=pi/2, duration=rf_duration, slice_thickness=slice_thickness, system=system,
    return_gz=True
)

# 180 degree refocussing pulse
rf_refocussing = pp.make_sinc_pulse(
    flip_angle=pi,       # 180°
    duration=rf_duration,   # keep duration -> doubles amplitude
    system=system,
    use='refocusing'
)

# Define delays
delay_te_1 = te / 2 - rf_excitation.shape_dur / 2 - rf_refocussing.shape_dur / 2
delay_te_2 = te / 2 - rf_refocussing.shape_dur / 2 - adc_duration / 2

# Define readout gradient and prewinder
grad_ro = pp.make_trapezoid(
    channel='x', 
    system=system, 
    flat_area=n_ro * delta_k, 
    flat_time=adc_duration
)
grad_ro_pre = pp.make_trapezoid(
    channel='x', 
    system=system, 
    area=grad_ro.area / 2 + delta_k / 2, 
    duration=delay_te_1
)

# Define adc event
adc = pp.make_adc(
    num_samples=n_ro, 
    system=system, 
    duration=adc_duration, 
    delay=delay_te_2
)

# TE/2 delay included in readout gradient
grad_ro.delay = delay_te_2 - grad_ro.rise_time
# Define TR as the time delay until the next ADC window/readout
delay_tr = tr - te - pp.calc_rf_center(rf_excitation)[0]

pe_flat_area = n_pe * (delta_k / 2)
pe_area_values = np.linspace(-1, 1, n_pe) * pe_flat_area

# Iterate over phase encoding steps
for pe_area in pe_area_values:
    # Define phase encoding gradient
    # Precomputed area, duration equals slice select rephaser
    grad_pe = pp.make_trapezoid(
        channel='y', 
        system=system, 
        area=pe_area, 
        duration=delay_te_1
    )
    
    # Add sequence blocks
    if slice_select:
        seq.add_block(rf_excitation, grad_slice)
    else:
        seq.add_block(rf_excitation)
    seq.add_block(grad_ro_pre, grad_pe)
    seq.add_block(rf_refocussing)
    seq.add_block(adc, grad_ro)
    seq.add_block(pp.make_delay(delay_tr))

seq.set_definition('Name', 'cartesian spin-echo')

# %%
# Check sequence timing and plot
ok, e = seq.check_timing()
seq.plot(time_disp='ms', time_range=(0, 0.03)) if ok else print(e)

# %%
# Print k-space




# %% 
# Write sequence
seq.write(f'./export/se_cartesian_{n_pe}-pe.seq')
# %%
