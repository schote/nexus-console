"""Constructor for spin-echo spectrum sequence with projection gradient."""

# %%
from math import pi

import pypulseq as pp

from console.utilities.sequences.system_settings import raster
from console.utilities.sequences.system_settings import system as default_system


def constructor(
    fov: float = 0.24,
    readout_bandwidth: float = 20e3,
    echo_time: float = 12e-3,
    gradient_correction: float = 0.0,
    num_samples: int = 120,
    rf_duration: float = 400e-6,
    channel: str = "x",
    use_sinc: bool = False,
    system: pp.Opts = default_system,
) -> pp.Sequence:
    """Construct spin echo spectrum sequence with projection gradient (1D).

    Parameters
    ----------
    fov, optional
        Field of view in m
    readout_bandwidth, optional
        Readout bandwidth in Hz
    echo_time, optional
        Time between center of 90 degree pulse and center of ADC in s
    gradient_correction, optional
        Additional delay to account for gradient system delays in s
    num_samples, optional
        Number of data points to acquire
    rf_duration, optional
        Duration of the RF pulses in s
    channel, optional
        Gradient channel to use for projection
    use_sinc, optional
        RF pulse type, if true: sinc pulse is used, rect otherwise
    system, optional
        Sequence system to be used for sequence construction

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
    seq.set_definition("readout_bandwidth_in_Hz", readout_bandwidth)
    seq.set_definition("fov_in_m", fov)
    seq.set_definition("te_in_s", echo_time)
    seq.set_definition("gradient_correction_in_s", gradient_correction)
    seq.set_definition("projection_channel", channel)

    # Define RF pulses for excitation and refocusing
    if use_sinc:
        rf_90 = pp.make_sinc_pulse(system=system, flip_angle=pi / 2, duration=rf_duration, apodization=0.5,
                                   delay=system.rf_dead_time)
        rf_180 = pp.make_sinc_pulse(system=system, flip_angle=pi, duration=rf_duration, apodization=0.5,
                                    delay=system.rf_dead_time)
    else:
        rf_90 = pp.make_block_pulse(system=system, flip_angle=pi / 2, duration=rf_duration,
                                    delay=system.rf_dead_time)
        rf_180 = pp.make_block_pulse(system=system, flip_angle=pi, duration=rf_duration,
                                     delay=system.rf_dead_time)

    # Define ADC duration
    adc_duration = num_samples / readout_bandwidth

    # Define readout gradient duration and amplitude
    g_ro_duration = adc_duration + gradient_correction
    g_ro_amplitude = num_samples / fov / adc_duration

    # Define readout gradient
    g_ro = pp.make_trapezoid(system=system, channel=channel, amplitude=g_ro_amplitude, flat_time=g_ro_duration)

    # Define readout prewinder
    g_ro_prew = pp.make_trapezoid(
        system=system,
        channel=channel,
        area=g_ro.area / 2,
        duration=pp.calc_duration(g_ro) / 2,
    )

    # Define ADC event
    adc = pp.make_adc(
        num_samples=num_samples,
        duration=adc_duration,
        system=system,
        delay=gradient_correction + g_ro.rise_time,
    )

    # Calculate delays to achieve desired echo time
    te_delay_1 = raster(echo_time / 2 - rf_duration - rf_90.ringdown_time - rf_180.delay
                        - pp.calc_duration(g_ro_prew),
                        precision=system.grad_raster_time)
    te_delay_2 = raster(echo_time / 2 - rf_duration / 2 - adc_duration / 2 - rf_180.ringdown_time
                        - adc.dead_time - gradient_correction - g_ro.rise_time,
                        precision=system.grad_raster_time)


    # Construct sequence
    seq.add_block(rf_90)
    seq.add_block(g_ro_prew)
    seq.add_block(pp.make_delay(te_delay_1))
    seq.add_block(rf_180)
    seq.add_block(pp.make_delay(te_delay_2))
    seq.add_block(g_ro, adc)

    return seq
