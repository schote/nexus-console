"""Constructor for spin-echo spectrum sequence."""
from math import pi

import pypulseq as pp

from console.utilities.sequences.system_settings import system


def constructor(
    rf_duration: float = 200e-6,
    dead_time: float = 2e-3,
    adc_duration: float = 4e-3,
    use_sinc: bool = False,
    time_bw_product: float = 4,
    flip_angle: float = pi/2,
    ) -> pp.Sequence:
    """Construct FID sequence.

    Parameters
    ----------
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
        Sequence timing check failed
    """
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "fid")

    if use_sinc:
        rf_90 = pp.make_sinc_pulse(system=system, flip_angle=flip_angle, duration=rf_duration, time_bw_product=time_bw_product)
    else:
        rf_90 = pp.make_block_pulse(system=system, flip_angle=flip_angle, duration=rf_duration)

    adc = pp.make_adc(
        num_samples=int(adc_duration/system.adc_raster_time),  # Is not taken into account atm
        duration=adc_duration,
        system=system,
    )

    ring_down_delay = pp.make_delay(
        round((dead_time) / 1e-6) * 1e-6
    )

    seq.add_block(rf_90)
    seq.add_block(ring_down_delay)
    seq.add_block(adc)

    return seq
