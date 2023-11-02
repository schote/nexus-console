"""Constructor for spin-echo spectrum sequence with projection gradient."""
# %%
from math import pi

import pypulseq as pp

# Definition of constants
GRAD_RISE_TIME = 200e-6

# Define system
system = pp.Opts(
    # rf_ringdown_time=100e-6,  # Time delay at the beginning of an RF event
    rf_dead_time=20e-6,  # time delay at the end of RF event
    # adc_dead_time=200e-6,  # time delay at the beginning of ADC event
)


def constructor(
    fov: float = 0.25, 
    readout_bandwidth: float = 20e3,
    echo_time: float = 12e-3,
    gradient_correction: float = 600e-6,
    num_samples: int = 110,
    rf_duration: float = 400e-6, 
    channel: str = "x", 
    use_sinc: bool = False
) -> pp.Sequence:
    """Construct spin echo spectrum sequence with projection gradient (1D).

    Parameters
    ----------
    fov, optional
        Field of view in m, by default 0.025
    te, optional
        Echo time in s, by default 12e-3
    rf_duration, optional
        RF duration in s, by default 400e-6
    use_sinc, optional
        RF pulse type, if true sinc pulse is used, rect otherwise, by default True

    Returns
    -------
        Pypulseq ``Sequence`` instance

    Raises
    ------
    ValueError
        Sequence time check failed
    """
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "se_projection")

    if use_sinc:
        rf_90 = pp.make_sinc_pulse(system=system, flip_angle=pi / 2, duration=rf_duration, apodization=0.5)
        rf_180 = pp.make_sinc_pulse(system=system, flip_angle=pi, duration=rf_duration, apodization=0.5)
    else:
        rf_90 = pp.make_block_pulse(system=system, flip_angle=pi / 2, duration=rf_duration)
        rf_180 = pp.make_block_pulse(system=system, flip_angle=pi, duration=rf_duration)

    adc_duration = num_samples / readout_bandwidth
    gradient_duration = adc_duration + gradient_correction
    k_width = num_samples / fov

    # Readout gradient
    gradient = pp.make_trapezoid(
        system=system, channel=channel, flat_area=k_width, flat_time=gradient_duration, rise_time=GRAD_RISE_TIME
    )
    # Prephaser gradient: Same amplitude (180° pulse inverts), halve of the duration
    # prephaser = pp.make_trapezoid(
    #     system=system, channel=channel, flat_area=k_width/2, flat_time=gradient_duration/2, rise_time=GRAD_RISE_TIME
    # )
    # prephaser.flat_time += gradient_correction / 2
    prephaser = pp.make_trapezoid(
        system=system, channel=channel, area=gradient.area/2, duration=pp.calc_duration(gradient)/2, rise_time=GRAD_RISE_TIME
    )

    adc = pp.make_adc(
        num_samples=1000,  # Is not taken into account atm
        duration=adc_duration,
        system=system,
        delay=gradient_correction+GRAD_RISE_TIME,
    )

    # Calculate delays
    te_delay_1 = pp.make_delay(echo_time / 2 - rf_duration - pp.calc_duration(prephaser))
    te_delay_2 = pp.make_delay(echo_time / 2 - rf_duration / 2 - adc_duration / 2 - gradient_correction)

    seq.add_block(rf_90)
    seq.add_block(prephaser)
    seq.add_block(te_delay_1)
    seq.add_block(rf_180)
    seq.add_block(te_delay_2)
    seq.add_block(gradient, adc)

    # Check sequence timing in each iteration
    # check_passed, err = seq.check_timing()
    # if not check_passed:
    #     raise ValueError("Sequence timing check failed: ", err)

    return seq


# %%
seq = constructor(echo_time=20e-3)
# %%
