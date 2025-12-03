"""Constructor for spin-echo-based frequency calibration sequence."""
from math import pi

import numpy as np
import pypulseq as pp

from console.utilities.sequences.system_settings import system


def constructor(
    n_steps: int = 10,
    flip_angle_range=(pi / 4, 3 * pi / 2),
    repetition_time: float = 1,
    echo_time: float = 20e-3,
    rf_duration: float = 400e-6,
    acq_bandwidth: float | int = 50e3,
    use_sinc: bool = False
) -> tuple[pp.Sequence, np.ndarray]:
    """Construct transmit adjust sequence.

    Parameters
    ----------
    n_steps
        Number of flip angles
    flip_angle_range
        Range of flip angles in rad
    repetition_time
        Repetition time in s
    echo_time
        Echo time in s
    rf_duration
        RF duration in s
    acq_bandwidth
        Acquisition bandwidth in Hz
    use_sinc
        Use sinc pulse if True, block pulse otherwise

    Returns
    -------
        Pypulseq ``Sequence`` instance and flip angles in rad

    Raises
    ------
    ValueError
        Sequence timing check failed
    """
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "tx_adjust")

    adc = pp.make_adc(
        num_samples=512,
        dwell = 1 / acq_bandwidth,
        system=system,
    )
    adc_duration = pp.calc_duration(adc)

    # Define flip angles
    flip_angles = np.linspace(flip_angle_range[0], flip_angle_range[1], n_steps, endpoint=True)

    for angle in flip_angles:
        if use_sinc:
            rf_90 = pp.make_sinc_pulse(system=system, flip_angle=angle, duration=rf_duration,
                                       delay=system.rf_dead_time)
            rf_180 = pp.make_sinc_pulse(system=system, flip_angle=angle * 2, duration=rf_duration,
                                        delay=system.rf_dead_time)
        else:
            rf_90 = pp.make_block_pulse(system=system, flip_angle=angle, duration=rf_duration,
                                        delay=system.rf_dead_time)
            rf_180 = pp.make_block_pulse(system=system, flip_angle=angle * 2, duration=rf_duration,
                                         delay=system.rf_dead_time)

        te_delay_1 = echo_time / 2 - rf_duration - rf_90.ringdown_time - rf_180.delay
        te_delay_2 = (echo_time - rf_duration - adc_duration) / 2 - rf_180.ringdown_time

        _start_time = sum(seq.block_durations.values())
        seq.add_block(rf_90)
        seq.add_block(pp.make_delay(te_delay_1))
        seq.add_block(rf_180)
        seq.add_block(pp.make_delay(te_delay_2))
        seq.add_block(adc)

        # calculate TR delay
        _duration_step = sum(seq.block_durations.values()) - _start_time
        delay_tr = repetition_time - _duration_step

        seq.add_block(pp.make_delay(delay_tr))

    return seq, flip_angles
