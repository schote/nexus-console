"""Constructor for spin-echo spectrum sequence."""
from math import pi

import pypulseq as pp

from console.utilities.sequences.system_settings import system


def constructor(
    echo_time: float = 12e-3,
    rf_duration: float = 400e-6,
    adc_ro_duration: float = 4e-3,
    adc_noise_duration: float = 1.0,
) -> pp.Sequence:
    """Construct spin echo spectrum sequence.

    Parameters
    ----------
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
        Sequence timing check failed
    """
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "se_spectrum")

    rf_90 = pp.make_block_pulse(system=system, flip_angle=pi / 2, duration=rf_duration)
    rf_180 = pp.make_block_pulse(system=system, flip_angle=pi, duration=rf_duration)

    adc_ro = pp.make_adc(
        num_samples=int(adc_ro_duration/system.adc_raster_time),
        duration=adc_ro_duration,
        system=system,
    )

    adc_noise = pp.make_adc(
        num_samples=int(adc_noise_duration/system.adc_raster_time),
        duration=adc_noise_duration,
        system=system,
    )

    te_delay_1 = pp.make_delay(echo_time / 2 - rf_duration - rf_90.ringdown_time - rf_180.dead_time)
    te_delay_2 = pp.make_delay(echo_time / 2 - rf_duration / 2 - adc_ro_duration / 2 - rf_180.ringdown_time)

    seq.add_block(rf_90)
    seq.add_block(te_delay_1)
    seq.add_block(rf_180)
    seq.add_block(te_delay_2)
    seq.add_block(adc_ro)
    seq.add_block(pp.make_delay(0.1))
    seq.add_block(adc_noise)

    return seq
