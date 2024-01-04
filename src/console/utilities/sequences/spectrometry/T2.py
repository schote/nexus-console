"""Constructor for spin-echo spectrum sequence."""
from math import pi
import numpy as np

import pypulseq as pp

from console.utilities.sequences.system_settings import system


def constructor(
    echo_time_range: tuple[float] = (10e-3, 100e-3),
    num_steps: int = 10,
    repetition_time: float = 600e-3,
    rf_duration: float = 400e-6,
    adc_duration: float = 4e-3
    ) -> tuple[pp.Sequence, np.ndarray]:
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
    seq.set_definition("Name", "te-variation")

    rf_90 = pp.make_block_pulse(system=system, flip_angle=pi / 2, duration=rf_duration)
    rf_180 = pp.make_block_pulse(system=system, flip_angle=pi, duration=rf_duration)

    # num_samples = int(adc_duration/system.adc_raster_time)
    adc = pp.make_adc(
        num_samples=1000,  # Is not taken into account atm
        duration=adc_duration,
        system=system,
    )

    te_values = np.linspace(echo_time_range[0], echo_time_range[1], num=num_steps)

    for echo_time in te_values:

        te_delay_1 = pp.make_delay(
            round((echo_time / 2 - rf_duration - rf_90.ringdown_time - rf_180.dead_time) / 1e-6) * 1e-6
        )
        te_delay_2 = pp.make_delay(
            round((echo_time / 2 - rf_duration / 2 - adc_duration / 2 - rf_180.ringdown_time - adc.dead_time) / 1e-6) * 1e-6
        )
        tr_delay = pp.make_delay(
            round((repetition_time - echo_time - adc_duration / 2 - rf_90.dead_time) / 1e-6) * 1e-6
        )

        seq.add_block(rf_90)
        seq.add_block(te_delay_1)
        seq.add_block(rf_180)
        seq.add_block(te_delay_2)
        seq.add_block(adc)
        seq.add_block(tr_delay)

        # check_passed, err = seq.check_timing()
        # if not check_passed:
        #     print("Check failed for echo time: ", echo_time)

    seq.set_definition(key="te_values", value=te_values)

    # Check sequence timing in each iteration
    check_passed, err = seq.check_timing()
    if not check_passed:
        raise ValueError("Sequence timing check failed: ", err)

    return seq, te_values
