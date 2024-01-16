"""Constructor for 3D TSE Imaging sequence."""
# %%
from math import pi

import numpy as np
import pypulseq as pp

from console.spcm_control.interface_acquisition_parameter import Dimensions
from console.utilities.sequences.system_settings import system

default_fov = Dimensions(x=220e-3, y=220e-3, z=225e-3)
default_encoding = Dimensions(x=70, y=70, z=49)


def constructor(
    echo_time: float = 15e-3,
    repetition_time: float = 600e-3,
    etl: int = 7,
    rf_duration: float = 400e-6,
    gradient_correction: float = 510e-6,
    ro_bandwidth: float = 20e3,
    fov: Dimensions = default_fov,
    n_enc: Dimensions = default_encoding,
) -> tuple[pp.Sequence, list]:
    """Construct 3D turbo spin echo sequence.

    Parameters
    ----------
    echo_time, optional
        Time constant between center of 90 degree pulse and center of ADC, by default 15e-3
    repetition_time, optional
        Time constant between two subsequent 90 degree pulses (echo trains), by default 600e-3
    etl, optional
        Echo train length, by default 7
    rf_duration, optional
        Duration of the RF pulses (90 and 180 degree), by default 400e-6
    gradient_correction, optional
        Time constant to center ADC event, by default 510e-6
    ro_bandwidth, optional
        Readout bandwidth in Hz, by default 20e3
    fov, optional
        Field of view per dimension, by default default_fov
    n_enc, optional
        Number of encoding steps per dimension, by default default_encoding

    Returns
    -------
        Pulseq sequence and a list which describes the trajectory
    """
    seq = pp.Sequence(system)
    seq.set_definition("Name", "tse_3d")

    # Definition of RF pulses
    rf_90 = pp.make_block_pulse(system=system, flip_angle=pi / 2, duration=rf_duration, use="excitation")
    rf_180 = pp.make_block_pulse(system=system, flip_angle=pi, duration=rf_duration, use="refocusing")

    # ADC duration
    adc_duration = n_enc.x / ro_bandwidth

    # Define readout gradient and prewinder
    grad_ro = pp.make_trapezoid(
        channel="x",
        system=system,
        flat_area=n_enc.x / fov.x,
        flat_time=adc_duration + gradient_correction,
    )

    ro_pre_duration = (pp.calc_duration(grad_ro) - gradient_correction) / 2

    grad_ro_pre = pp.make_trapezoid(
        channel="x",
        system=system,
        area=grad_ro.area / 2,
        duration=ro_pre_duration,
    )

    adc = pp.make_adc(
        system=system,
        num_samples=int(adc_duration/system.adc_raster_time),
        duration=adc_duration,
        delay=gradient_correction + grad_ro.rise_time,
    )

    def grad_raster(val: float) -> float:
        """Fit value to gradient raster."""
        # return round(val / system.grad_raster_time) * system.grad_raster_time
        return np.ceil(val / system.grad_raster_time) * system.grad_raster_time

    # Calculate delays
    # Note: RF dead-time is contained in RF delay
    # Delay duration between RO prephaser after initial 90 degree RF and 180 degree RF pulse
    tau_1 = echo_time / 2 - rf_duration - rf_90.ringdown_time - rf_180.delay - ro_pre_duration
    # Delay duration between Gy, Gz prephaser and readout
    tau_2 = (echo_time - rf_duration - pp.calc_duration(grad_ro)) / 2 - rf_180.ringdown_time - ro_pre_duration
    # Delay duration between readout and Gy, Gz gradient rephaser
    tau_3 = (echo_time - rf_duration - pp.calc_duration(grad_ro)) / 2 - rf_180.delay - ro_pre_duration
    # Delay between echo trains
    tr_delay = repetition_time - echo_time - adc_duration / 2 - rf_90.delay

    # Calculate center out trajectory
    pe0 = np.arange(n_enc.y) - int((n_enc.y - 1) / 2)
    pe1 = np.arange(n_enc.z) - int((n_enc.z - 1) / 2)

    pe0_ordered = pe0[np.argsort(np.abs(pe0 - 0.5))]
    pe1_ordered = pe1[np.argsort(np.abs(pe1 - 0.5))]

    pe_traj = np.stack([grid.flatten() for grid in np.meshgrid(pe0_ordered, pe1_ordered, indexing='ij')], axis=-1)

    pe_traj[:, 0] / fov.y
    pe_traj[:, 1] / fov.z

    num_trains = int(np.ceil(pe_traj.shape[0] / etl))
    trains = [pe_traj[k*etl:(k+1)*etl] for k in range(num_trains)]

    ro_counter = 0

    for train in trains:

        seq.add_block(rf_90)
        seq.add_block(grad_ro_pre)
        seq.add_block(pp.make_delay(grad_raster(tau_1)))

        for echo in train:

            pe_0, pe_1 = echo

            seq.add_block(rf_180)

            seq.add_block(
                pp.make_trapezoid(channel="y", area=-pe_0, duration=ro_pre_duration, system=system),
                pp.make_trapezoid(channel="z", area=-pe_1, duration=ro_pre_duration, system=system)
            )

            seq.add_block(pp.make_delay(grad_raster(tau_2)))

            seq.add_block(grad_ro, adc)

            seq.add_block(pp.make_delay(grad_raster(tau_3)))

            seq.add_block(
                pp.make_trapezoid(channel="y", area=pe_0, duration=ro_pre_duration, system=system),
                pp.make_trapezoid(channel="z", area=pe_1, duration=ro_pre_duration, system=system)
            )

            ro_counter += 1

            # Add TR after echo train, if not the last readout
            if ro_counter < n_enc.y * n_enc.z:
                seq.add_block(pp.make_delay(round(tr_delay / 1e-6) * 1e-6))

    # Calculate some sequence measures
    train_duration_tr = (seq.duration()[0] + tr_delay) / len(trains)
    train_duration = train_duration_tr - tr_delay

    # Add measures to sequence definition
    seq.set_definition("n_total_trains", len(trains))
    seq.set_definition("train_duration", train_duration)
    seq.set_definition("train_duration_tr", train_duration_tr)
    seq.set_definition("tr_delay", tr_delay)

    return (seq, trains)
