"""Constructor for spin-echo sequence to measure global T2 relaxation."""
from math import pi

import numpy as np
import pypulseq as pp

from console.utilities.sequences.system_settings import raster
from console.utilities.sequences.system_settings import system as default_system


def constructor(
    echo_time_range: tuple[float, float] = (10e-3, 100e-3),
    num_steps: int = 10,
    repetition_time: float = 600e-3,
    rf_duration: float = 400e-6,
    num_samples: int = 64,
    acq_bandwidth: float | int = 20e3,
    system: pp.Opts = default_system,
    ) -> tuple[pp.Sequence, np.ndarray]:
    """Construct spin echo T2 relaxation sequence.

    Parameters
    ----------
    echo_time_range
        Range of echo times in s
    num_steps
        Number of echo times to sample
    repetition_time
        Time between two subsequent 90 degree pulses in s
    rf_duration
        Duration of the RF pulses in s
    num_samples
        Number of data points to acquire
    acq_bandwidth
        Bandwidth of the acquisition in Hz
    system
        Sequence system to be used for sequence construction

    Returns
    -------
        Pypulseq ``Sequence`` instance and array of echo times

    Raises
    ------
    ValueError
        Sequence timing check failed
    """
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "te-variation")

    # Define RF pulses for excitation and refocusing
    rf_90 = pp.make_block_pulse(system=system, flip_angle=pi / 2, phase_offset=0, duration=rf_duration,
                                delay=system.rf_dead_time)
    rf_180 = pp.make_block_pulse(system=system, flip_angle=pi, phase_offset=pi / 2, duration=rf_duration,
                                 delay=system.rf_dead_time)

    # Define ADC duration
    adc_duration = raster(val=num_samples / acq_bandwidth, precision=system.adc_raster_time)

    # Define ADC event
    adc = pp.make_adc(
        num_samples=num_samples,
        duration=adc_duration,
        system=system,
    )

    # Define array of echo times
    te_values = np.linspace(echo_time_range[0], echo_time_range[1], num=num_steps)

    for echo_time in te_values:
        # Calculate delays to achieve desired echo time
        te_delay_1 = raster(
            echo_time / 2 - rf_duration - rf_90.ringdown_time - rf_180.delay,
            precision=system.grad_raster_time
        )
        te_delay_2 = raster(
            echo_time / 2 - rf_duration / 2 - adc_duration / 2 - rf_180.ringdown_time - adc.dead_time,
            precision=system.grad_raster_time
        )

        _start_time = sum(seq.block_durations.values())
        seq.add_block(rf_90)
        seq.add_block(pp.make_delay(te_delay_1))
        seq.add_block(rf_180)
        seq.add_block(pp.make_delay(te_delay_2))
        seq.add_block(adc)

        # calculate TR delay
        _duration_te_step = sum(seq.block_durations.values()) - _start_time
        delay_tr = repetition_time - _duration_te_step
        delay_tr = raster(delay_tr, precision=system.grad_raster_time)
        seq.add_block(pp.make_delay(delay_tr))


    seq.set_definition(key="te_values", value=te_values)

    return seq, te_values
