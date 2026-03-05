"""Constructor for spin-echo spectrum sequence."""
from math import pi

import pypulseq as pp

from console.utilities.sequences.system_settings import system as default_system


def constructor(
    rf_duration: float = 200e-6,
    num_samples: int = 256,
    acq_bandwidth: float | int = 20e3,
    use_sinc: bool = False,
    time_bw_product: float = 4,
    flip_angle: float = pi / 2,
    system: pp.Opts = default_system,
    ) -> pp.Sequence:
    """Construct FID sequence.

    Parameters
    ----------
    rf_duration, optional
        RF duration in s, by default 200e-6
    num_samples, optional
        Number of ADC sample points, by default 256
    acq_bandwidth, optional
        Acquisition bandwidth in Hz, by default 20e3
    use_sinc, optional
        If set, sinc RF pulse is used, otherwise block pulse, by default False
    time_bw_product, optional
        Time bandwidth product, by default 4
    flip_angle, optional
        Flip angle of RF pulse, by default pi/2
    system, optional
        Sequence system to be used for sequence construction, by default default_system

    Returns
    -------
        Pypulseq ``Sequence`` instance
    """
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "fid")

    # Define RF pulse for excitation
    if use_sinc:
        rf_90 = pp.make_sinc_pulse(
            system=system,
            flip_angle=flip_angle,
            duration=rf_duration,
            phase_offset=0,
            time_bw_product=time_bw_product,
            delay=system.rf_dead_time,
        )
    else:
        rf_90 = pp.make_block_pulse(
            system=system,
            flip_angle=flip_angle,
            duration=rf_duration,
            phase_offset=0,
            delay=system.rf_dead_time,
        )

    # Define ADC event
    adc = pp.make_adc(
        num_samples=num_samples,
        dwell=1 / acq_bandwidth,
        phase_offset=0,
        system=system,
    )

    seq.add_block(rf_90)
    seq.add_block(adc)

    return seq
