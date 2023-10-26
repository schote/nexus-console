"""Constructor for spin-echo spectrum sequence with projection gradient."""
from math import pi

import pypulseq as pp

# Definition of constants
ADC_DURATION = 4e-3
GRAD_RISE_TIME = 200e-6

# Define system
system = pp.Opts(
    rf_ringdown_time=100e-6,  # Time delay at the beginning of an RF event
    rf_dead_time=100e-6,  # time delay at the end of RF event
    adc_dead_time=200e-6,  # time delay at the beginning of ADC event
)


def constructor(
    fov: float = 0.25, echo_time: float = 12e-3, rf_duration: float = 400e-6, use_sinc: bool = True
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

    num_samples = 256
    k_width = num_samples / fov

    gradient = pp.make_trapezoid(
        system=system, channel="x", flat_area=k_width, flat_time=ADC_DURATION, rise_time=GRAD_RISE_TIME
    )

    adc = pp.make_adc(
        num_samples=1000,  # Is not taken into account atm
        duration=ADC_DURATION,
        system=system,
    )

    te_delay_1 = pp.make_delay(echo_time / 2 - rf_duration)
    te_delay_2 = pp.make_delay(echo_time / 2 - rf_duration / 2 - ADC_DURATION / 2)

    seq.add_block(rf_90)
    seq.add_block(te_delay_1)
    seq.add_block(rf_180)
    seq.add_block(te_delay_2)
    seq.add_block(gradient, adc)

    # Check sequence timing in each iteration
    check_passed, err = seq.check_timing()
    if not check_passed:
        raise ValueError("Sequence timing check failed: ", err)

    return seq
