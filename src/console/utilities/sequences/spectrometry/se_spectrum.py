"""Constructor for spin-echo spectrum sequence."""
from math import pi

import pypulseq as pp

from console.utilities.sequences.system_settings import raster, system


def constructor(
    echo_time: float = 12e-3,
    rf_duration: float = 400e-6,
    num_samples: int = 256,
    acq_bandwidth: float | int = 20e3,
    use_sinc: bool = False,
    time_bw_product: float = 4,
    use_fid: bool = True,
    ) -> pp.Sequence:
    """Construct spin echo spectrum sequence.

    Parameters
    ----------
    te, optional
        Echo time in s, by default 12e-3
    num_samples, optional
        Number of data points to acquire
    acq_bandwidth, optional
        bandwidth of the acquisition in Hz, inverse of the dwell time.
        total data acquisition time is num_samples/acq_bandwidth
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

    if use_fid:
        seq.set_definition("Name", "se_decay_spectrum")
    else:
        seq.set_definition("Name", "se_spectrum")

    if use_sinc:
        rf_90 = pp.make_sinc_pulse(
            system=system, flip_angle=pi / 2, phase_offset=0, duration=rf_duration, time_bw_product=time_bw_product
        )
        rf_180 = pp.make_sinc_pulse(
            system=system, flip_angle=pi, phase_offset=pi / 2, duration=rf_duration, time_bw_product=time_bw_product
        )
    else:
        rf_90 = pp.make_block_pulse(system=system, flip_angle=pi / 2, phase_offset=0, duration=rf_duration)
        rf_180 = pp.make_block_pulse(system=system, flip_angle=pi, phase_offset=pi / 2, duration=rf_duration)

    adc_duration = raster(val=num_samples / acq_bandwidth, precision=system.adc_raster_time)
    adc = pp.make_adc(
        num_samples=num_samples,
        duration=adc_duration,
        system=system,
    )

    te_delay_1 = raster(echo_time / 2 - rf_duration - rf_90.ringdown_time - rf_180.dead_time, 1e-6)
    if use_fid:
        te_delay_2 = raster(echo_time / 2 - rf_duration / 2 - rf_180.ringdown_time - adc.dead_time, 1e-6)
    else:
        te_delay_2 = raster(
            echo_time / 2 - rf_duration / 2 - adc_duration / 2 - rf_180.ringdown_time - adc.dead_time, 1e-6
        )

    seq.add_block(rf_90)
    seq.add_block(pp.make_delay(te_delay_1))
    seq.add_block(rf_180)
    seq.add_block(pp.make_delay(te_delay_2))
    seq.add_block(adc)

    return seq
