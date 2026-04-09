"""Constructor for spin-echo-based frequency calibration sequence."""
# %%
from math import pi

import numpy as np
import pypulseq as pp

from console.utilities.sequences.system_settings import raster
from console.utilities.sequences.system_settings import system as default_system


def constructor(
    n_steps: int = 10,
    flip_angle_range=(pi / 4, 3 * pi / 2),
    repetition_time: float = 4,
    rf_duration: float = 200e-6,
    use_sinc: bool = False,
    num_adc_samples: int = 256,
    acq_bandwidth: float | int = 20e3,
    ring_down_time: float = 2e-3,
    system: pp.Opts = default_system,
) -> tuple[pp.Sequence, np.ndarray]:
    """Construct transmit adjust sequence.

    Parameters
    ----------
    n_steps, optional
        Number of flip angles
    flip_angle_range, optional
        Range of flip angles in rad
    repetition_time, optional
        Repetition time in s
    rf_duration, optional
        RF pulse duration in s
    use_sinc, optional
        RF pulse type, if true sinc pulse is used, rect otherwise
    num_adc_samples, optional
        Number of ADC samples
    acq_bandwidth, optional
        Acquisition bandwidth in Hz
    ring_down_time, optional
        RF ring down time in s
    system, optional
        Sequence system to be used for sequence construction

    Returns
    -------
        Pypulseq ``Sequence`` instance and flip angles in rad

    Raises
    ------
    ValueError
        Sequence timing check failed
    """
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "tx_adjust_fid")
    seq.system.rf_ringdown_time = ring_down_time

    adc = pp.make_adc(
        num_samples=num_adc_samples,
        dwell=1 / acq_bandwidth,
        system=system,
    )

    # Define flip angles
    flip_angles = np.linspace(flip_angle_range[0], flip_angle_range[1], n_steps, endpoint=True)

    for angle in flip_angles:
        if use_sinc:
            rf_90 = pp.make_sinc_pulse(system=system, flip_angle=angle, duration=rf_duration, apodization=0.5,
                                       delay=system.rf_dead_time)
        else:
            rf_90 = pp.make_block_pulse(system=system, flip_angle=angle, duration=rf_duration,
                                        delay=system.rf_dead_time)
        _start_time = sum(seq.block_durations.values())
        seq.add_block(rf_90)
        seq.add_block(adc)

        # calculate TR delay
        _duration_step = sum(seq.block_durations.values()) - _start_time
        delay_tr = repetition_time - _duration_step
        delay_tr = raster(delay_tr, precision=system.grad_raster_time)
        seq.add_block(pp.make_delay(delay_tr))

    return seq, flip_angles
