"""Constructor for spin-echo spectrum sequence with projection gradient."""
# %%
from math import pi

import pypulseq as pp

from console.utilities.sequences.system_settings import system


def constructor(
    fov: float = 0.25,
    readout_bandwidth: float = 20e3,
    echo_time: float = 12e-3,
    gradient_correction: float = 600e-6,
    num_samples: int = 110,
    rf_duration: float = 400e-6,
    channel: str = "x",
    use_sinc: bool = False,
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
        system=system,
        channel=channel,
        flat_area=k_width,
        flat_time=gradient_duration
    )

    prephaser = pp.make_trapezoid(
        system=system,
        channel=channel,
        area=gradient.area / 2,
        duration=pp.calc_duration(gradient) / 2,
    )

    adc = pp.make_adc(
        num_samples=int(adc_duration / system.adc_raster_time),
        duration=adc_duration,
        system=system,
        delay=gradient_correction + gradient.rise_time,
    )

    # Calculate delays
    te_delay_1_val = echo_time / 2 - rf_duration - rf_90.ringdown_time - rf_180.dead_time
    te_delay_1 = pp.make_delay(round(te_delay_1_val / 1e-6) * 1e-6)
    te_delay_2_val = echo_time / 2 - rf_duration / 2 - adc_duration / 2 - rf_180.ringdown_time - adc.dead_time
    te_delay_2 = pp.make_delay(round((te_delay_2_val - gradient_correction) / 1e-6) * 1e-6)

    # construct sequence
    seq.add_block(rf_90)
    seq.add_block(prephaser)
    seq.add_block(te_delay_1)
    seq.add_block(rf_180)
    seq.add_block(te_delay_2)
    seq.add_block(gradient, adc)

    return seq
