"""Constructor for 3D TSE Imaging sequence.

TODO: add sampling patterns (elliptical masks, partial fourier, CS)
TODO: add optional inversion pulse
TODO: add optional variable refocussing pulses (pass list rather than float)
TODO: move trajectory calculation to seperate file to sharew with other imaging experiments (needed?)

"""
# %%
from enum import Enum
from math import pi
import ismrmrd
import numpy as np

import numpy as np
import pypulseq as pp

from console.interfaces.interface_acquisition_parameter import Dimensions
from console.utilities.sequences.system_settings import raster, system


class Trajectory(Enum):
    """Trajectory type enum."""

    INOUT = 1
    OUTIN = 2
    LINEAR = 3


default_fov = Dimensions(x=220e-3, y=220e-3, z=225e-3)
default_encoding = Dimensions(x=70, y=70, z=49)


def constructor(
    echo_time: float = 15e-3,
    repetition_time: float = 600e-3,
    etl: int = 7,
    dummies: int = 0,
    rf_duration: float = 400e-6,
    ramp_duration: float = 200e-6,
    gradient_correction: float = 0.,
    ro_bandwidth: float = 20e3,
    fov: Dimensions = default_fov,
    n_enc: Dimensions = default_encoding,
    echo_shift: float = 0.0,
    trajectory: Trajectory = Trajectory.INOUT,
    excitation_angle: float = pi / 2,
    excitation_phase: float = 0.,
    refocussing_angle: float = pi,
    refocussing_phase: float = pi / 2,
    inversion_pulse: bool = False,
    inversion_time: float = 50e-3,
    inversion_angle: float = pi,
    channel_ro: str = "y",
    channel_pe1: str = "z",
    channel_pe2: str = "x",
    noise_scan: bool = False
) -> tuple[pp.Sequence, ismrmrd.xsd.ismrmrdHeader]:
    """Construct 3D turbo spin echo sequence.

    Parameters
    ----------
    echo_time, optional
        Time constant between center of 90 degree pulse and center of ADC, by default 15e-3
    repetition_time, optional
        Time constant between two subsequent 90 degree pulses (echo trains), by default 600e-3
    etl, optional
        Echo train length, by default 7
    dummies, optional
        Number of dummy shots to acquire, default is 0
    rf_duration, optional
        Duration of the RF pulses (90 and 180 degree), by default 400e-6
    gradient_correction, optional
        Time constant to center ADC event, by default 510e-6
    adc_correction, optional
        Time constant which is added at the end of the ADC and readout gradient.
        This value is not taken into account for the prephaser calculation.
    ro_bandwidth, optional
        Readout bandwidth in Hz, by default 20e3
    fov, optional
        Field of view per dimension, by default default_fov
    n_enc, optional
        Number of encoding steps per dimension, by default default_encoding = Dimensions(x=70, y=70, z=49).
        If an encoding dimension is set to 1, the TSE sequence becomes a 2D sequence.
    trajectroy, optional
        The k-space trajectory, by default set to in-out, other currently implemented options are...
    excitation_angle, excitation_phase, optional
        set the flip angle and phase of the excitation pulse in radians, defaults to 90 degree flip angle, 0 phase
    refocussing_angle, refocussing_phase, optional
        Set the flip angle and phase of the refocussing pulse in radians,
        defaults to 180 degree flip angle, 90 degree phase
        TODO: allow this to be a list/array to vary flip angle along echo train.
    channel_ro, channel_pe1, channel_pe2, optional
        set the readout, phase1 and phase2 encoding directions, default to y, z and x.

    Returns
    -------
        Pulseq sequence and a list which describes the trajectory
    """
    system.rf_ringdown_time = 0
    seq = pp.Sequence(system)
    seq.set_definition("Name", "tse_3d")

    # check if channel labels are valid
    channel_valid = True
    if len(channel_ro) > 1 or len(channel_ro) == 0:
        channel_valid = False
        print("Invalid readout channel: %s" % (channel_ro))
    if len(channel_pe1) > 1 or len(channel_pe1) == 0:
        channel_valid = False
        print("Invalid pe1 channel: %s" % (channel_pe1))
    if len(channel_pe2) > 1 or len(channel_pe2) == 0:
        channel_valid = False
        print("Invalid pe2 channel: %s" % (channel_pe2))

    channel_ro = channel_ro.lower()
    channel_pe1 = channel_pe1.lower()
    channel_pe2 = channel_pe2.lower()  # set all channels to lower case

    if channel_ro not in ("x", "y", "z") or channel_pe1 not in ("x", "y", "z") or channel_pe2 not in ("x", "y", "z"):
        channel_valid = False
        print("Invalid axis orientation")
    if channel_ro == channel_pe1 or channel_ro == channel_pe2 or channel_pe1 == channel_pe2:
        channel_valid = False
        print("Error, multiple channels have the same gradient")
        print("Readout channel: %s, pe1 channel: %s, pe2 channel: %s" % (channel_ro, channel_pe1, channel_pe2))
    if not channel_valid:
        print("Defaulting to readout in y, pe1 in z, pe2 in x")
        channel_ro = "y"
        channel_pe1 = "z"
        channel_pe2 = "x"

    if (channel_ro == "x"):
        n_enc_ro = n_enc.x
        fov_ro = fov.x
        if channel_pe1 == "y":
            n_enc_pe1 = n_enc.y
            fov_pe1 = fov.y
            n_enc_pe2 = n_enc.z
            fov_pe2 = fov.z
        else:
            n_enc_pe1 = n_enc.z
            fov_pe1 = fov.z
            n_enc_pe2 = n_enc.y
            fov_pe2 = fov.y
    elif (channel_ro == "y"):
        n_enc_ro = n_enc.y
        fov_ro = fov.y
        if channel_pe1 == "x":
            n_enc_pe1 = n_enc.x
            fov_pe1 = fov.x
            n_enc_pe2 = n_enc.z
            fov_pe2 = fov.z
        else:
            n_enc_pe1 = n_enc.z
            fov_pe1 = fov.z
            n_enc_pe2 = n_enc.x
            fov_pe2 = fov.x
    else:
        n_enc_ro = n_enc.z
        fov_ro = fov.z
        if channel_pe1 == "y":
            n_enc_pe1 = n_enc.y
            fov_pe1 = fov.y
            n_enc_pe2 = n_enc.x
            fov_pe2 = fov.x
        else:
            n_enc_pe1 = n_enc.x
            fov_pe1 = fov.x
            n_enc_pe2 = n_enc.y
            fov_pe2 = fov.y

    # Calculate center out trajectory
    pe1 = np.arange(n_enc_pe1) - (n_enc_pe1 - 1) / 2
    pe2 = np.arange(n_enc_pe2) - (n_enc_pe2 - 1) / 2

    pe0_pos = np.arange(n_enc_pe1)
    pe1_pos = np.arange(n_enc_pe2)

    pe_points = np.stack([grid.flatten() for grid in np.meshgrid(pe1, pe2)], axis=-1)
    pe_positions = np.stack([grid.flatten() for grid in np.meshgrid(pe0_pos, pe1_pos)], axis=-1)

    pe_mag = np.sum(np.square(pe_points), axis=-1)  # calculate magnitude of all gradient combinations
    pe_mag_sorted = np.argsort(pe_mag)

    if trajectory is (Trajectory.INOUT or Trajectory.OUTIN):
        if trajectory is Trajectory.OUTIN:
            pe_mag_sorted = np.flip(pe_mag_sorted)

        pe_traj = pe_points[pe_mag_sorted, :]  # sort the points based on magnitude
        pe_order = pe_positions[pe_mag_sorted, :]  # kspace position for each of the gradients

    elif trajectory is Trajectory.LINEAR:
        center_pos = 1 / 2  # where the center of kspace should be in the echo train
        num_points = np.size(pe_mag_sorted)
        linear_pos = np.zeros(num_points, dtype=int) - 10
        center_point = int(np.round(np.size(pe_mag) * center_pos))
        odd_indices = 1
        even_indices = 1
        linear_pos[center_point] = pe_mag_sorted[0]

        for idx in range(1, num_points):
            # check if its in bounds first
            if center_point - (idx + 1) / 2 >= 0 and idx % 2:
                k_idx = center_point - odd_indices
                odd_indices += 1
            elif center_point + idx / 2 < num_points and idx % 2 == 0:
                k_idx = center_point + even_indices
                even_indices += 1
            elif center_point - (idx + 1) / 2 < 0 and idx % 2:
                k_idx = center_point + even_indices
                even_indices += 1
            elif center_point + idx / 2 >= num_points and idx % 2 == 0:
                k_idx = center_point - odd_indices
                odd_indices += 1
            else:
                print("Sorting error")
            linear_pos[k_idx] = pe_mag_sorted[idx]

        pe_traj = pe_points[linear_pos, :]  # sort the points based on magnitude
        pe_order = pe_positions[linear_pos, :]  # kspace position for each of the gradients
    else:
        raise ValueError("Invalid trajectory: ", trajectory)

    # calculate the required gradient area for each k-point
    pe_traj[:, 0] /= fov_pe1
    pe_traj[:, 1] /= fov_pe2

    # Divide all PE steps into echo trains
    num_trains = int(np.ceil(pe_traj.shape[0] / etl))
    trains = [pe_traj[k::num_trains, :] for k in range(num_trains)]

    # Create a list with the kspace location of every line of kspace acquired, in the order it is acquired
    trains_pos = [pe_order[k::num_trains, :] for k in range(num_trains)]

    # Definition of RF pulses
    rf_90 = pp.make_block_pulse(
        system=system,
        flip_angle=excitation_angle,
        phase_offset=excitation_phase,
        duration=rf_duration,
        use="excitation"
    )
    rf_180 = pp.make_block_pulse(
        system=system,
        flip_angle=refocussing_angle,
        phase_offset=refocussing_phase,
        duration=rf_duration,
        use="refocusing"
    )
    if inversion_pulse:
        rf_inversion = pp.make_block_pulse(
            system=system,
            flip_angle=inversion_angle,
            phase_offset=refocussing_phase,
            duration=rf_duration,
            use="refocusing"
        )

    # ADC duration
    adc_duration = n_enc_ro / ro_bandwidth

    # Define readout gradient and prewinder
    grad_ro = pp.make_trapezoid(
        channel=channel_ro,
        system=system,
        flat_area=n_enc_ro / fov_ro,
        rise_time=ramp_duration,
        fall_time=ramp_duration,
        # Add gradient correction time and ADC correction time
        flat_time=raster(adc_duration, precision=system.grad_raster_time),
    )
    # using the previous calculation for the amplitde, hacky, should find a better way
    grad_ro = pp.make_trapezoid(
        channel=channel_ro,
        system=system,
        amplitude=grad_ro.amplitude,
        rise_time=ramp_duration,
        fall_time=ramp_duration,
        # Add gradient correction time
        flat_time=raster(adc_duration + 2 * gradient_correction, precision=system.grad_raster_time),
    )

    # Calculate readout prephaser without correction times
    ro_pre_duration = pp.calc_duration(grad_ro) / 2

    grad_ro_pre = pp.make_trapezoid(
        channel=channel_ro,
        system=system,
        area=grad_ro.area / 2,
        rise_time=ramp_duration,
        fall_time=ramp_duration,
        duration=raster(ro_pre_duration, precision=system.grad_raster_time),
    )

    adc = pp.make_adc(
        system=system,
        num_samples=n_enc_ro,
        duration=raster(val=adc_duration, precision=system.adc_raster_time),
        # Add gradient correction time and ADC correction time
        delay=raster(val=2 * gradient_correction + grad_ro.rise_time, precision=system.adc_raster_time)
    )

    # Calculate delays
    # Note: RF dead-time is contained in RF delay
    # Delay duration between RO prephaser after initial 90 degree RF and 180 degree RF pulse
    tau_1 = echo_time / 2 - rf_duration - rf_90.ringdown_time - rf_180.delay - ro_pre_duration
    # Delay duration between Gy, Gz prephaser and readout
    tau_2 = (echo_time - rf_duration - adc_duration) / 2 - 2 * gradient_correction \
        - ramp_duration - rf_180.ringdown_time - ro_pre_duration + echo_shift
    # Delay duration between readout and Gy, Gz gradient rephaser
    tau_3 = (echo_time - rf_duration - adc_duration) / 2 - ramp_duration - rf_180.delay - ro_pre_duration - echo_shift

    for _ in range(dummies):
        if inversion_pulse:
            seq.add_block(rf_inversion)
            seq.add_block(pp.make_delay(raster(val=inversion_time - rf_duration, precision=system.grad_raster_time)))
        seq.add_block(rf_90)
        seq.add_block(pp.make_delay(raster(val=echo_time / 2 - rf_duration, precision=system.grad_raster_time)))
        for idx in range(etl):
            seq.add_block(rf_180)
            seq.add_block(pp.make_delay(raster(
                val=echo_time - rf_duration,
                precision=system.grad_raster_time
            )))
        if inversion_pulse:
            seq.add_block(pp.make_delay(raster(
                val=repetition_time - (etl + 0.5) * echo_time - rf_duration - inversion_time,
                precision=system.grad_raster_time
            )))
        else:
            seq.add_block(pp.make_delay(raster(
                val=repetition_time - (etl + 0.5) * echo_time - rf_duration,
                precision=system.grad_raster_time
            )))

    for train, position in zip(trains, trains_pos):
        if inversion_pulse:
            seq.add_block(rf_inversion)
            seq.add_block(pp.make_delay(raster(
                val=inversion_time - rf_duration,
                precision=system.grad_raster_time
            )))
        seq.add_block(rf_90)
        seq.add_block(grad_ro_pre)
        seq.add_block(pp.make_delay(raster(val=tau_1, precision=system.grad_raster_time)))

        for echo, pe_indices in zip(train, position):
            pe_1, pe_2 = echo

            seq.add_block(rf_180)

            seq.add_block(
                pp.make_trapezoid(
                    channel=channel_pe1,
                    area=-pe_1,
                    duration=ro_pre_duration,
                    system=system,
                    rise_time=ramp_duration,
                    fall_time=ramp_duration
                ),
                pp.make_trapezoid(
                    channel=channel_pe2,
                    area=-pe_2,
                    duration=ro_pre_duration,
                    system=system,
                    rise_time=ramp_duration,
                    fall_time=ramp_duration
                )
            )

            seq.add_block(pp.make_delay(raster(val=tau_2, precision=system.grad_raster_time)))

            # Cast index values from int32 to int, otherwise make_label function complains
            label_pe1 = pp.make_label(type="SET", label="LIN", value=int(pe_indices[0]))
            label_pe2 = pp.make_label(type="SET", label="PAR", value=int(pe_indices[1]))
            seq.add_block(grad_ro, adc, label_pe1, label_pe2)

            seq.add_block(
                pp.make_trapezoid(
                    channel=channel_pe1,
                    area=pe_1,
                    duration=ro_pre_duration,
                    system=system,
                    rise_time=ramp_duration,
                    fall_time=ramp_duration
                ),
                pp.make_trapezoid(
                    channel=channel_pe2,
                    area=pe_2,
                    duration=ro_pre_duration,
                    system=system,
                    rise_time=ramp_duration,
                    fall_time=ramp_duration
                )
            )

            seq.add_block(pp.make_delay(raster(val=tau_3, precision=system.grad_raster_time)))

        # recalculate TR each train because train length is not guaranteed to be constant
        tr_delay = repetition_time - echo_time * len(train) - adc_duration / 2 - ro_pre_duration \
            - tau_3 - rf_90.delay - rf_duration / 2 - ramp_duration

        if inversion_pulse:
            tr_delay -= inversion_time
        
        if noise_scan:
            noise_adc_dead_time = 50e-3
            noise_adc_dur = min(tr_delay-noise_adc_dead_time, 100e-3)
            noise_adc = pp.make_adc(
                system=system,
                num_samples=int((noise_adc_dur) / system.adc_raster_time),
                duration=raster(val=noise_adc_dur, precision=system.adc_raster_time),
                delay=noise_adc_dead_time
            )
            seq.add_block(noise_adc)
            post_noise_adc_delay = raster(tr_delay-noise_adc_dead_time-noise_adc_dur, system.block_duration_raster)
            if post_noise_adc_delay > 0:
                seq.add_block(pp.make_delay(post_noise_adc_delay))
        
        else:
            seq.add_block(pp.make_delay(raster(
                val=tr_delay,
                precision=system.block_duration_raster
            )))

    # Calculate some sequence measures
    train_duration_tr = (seq.duration()[0]) / len(trains)
    train_duration = train_duration_tr - tr_delay

    # Check labels
    labels = seq.evaluate_labels(evolution="adc")
    acq_pos = np.concatenate(trains_pos).T
    if not np.array_equal(labels["LIN"], acq_pos[0, :]):
        raise ValueError("LIN labels don't match actual acquisition positions.")
    if not np.array_equal(labels["PAR"], acq_pos[1, :]):
        raise ValueError("PAR labels don't match actual acquisition positions.")

    # Add measures and definitions to sequence definition
    seq.set_definition("n_total_trains", len(trains))
    seq.set_definition("train_duration", train_duration)
    seq.set_definition("train_duration_tr", train_duration_tr)
    seq.set_definition("tr_delay", tr_delay)

    seq.set_definition("encoding_dim", [n_enc_ro, n_enc_pe1, n_enc_pe2])
    seq.set_definition("encoding_fov", [fov_ro, fov_pe1, fov_pe2])
    seq.set_definition("channel_order", [channel_ro, channel_pe1, channel_pe2])

    # Create ISMRMRD header
    header = ismrmrd.xsd.ismrmrdHeader()

    # experimental conditions
    exp = ismrmrd.xsd.experimentalConditionsType()
    exp.H1resonanceFrequency_Hz = system.B0 * system.gamma / (2 * pi)
    header.experimentalConditions = exp

    # set fov and matrix size
    efov = ismrmrd.xsd.fieldOfViewMm() # kspace fov in mm
    efov.x = fov_ro * 1e3
    efov.y = fov_pe1 * 1e3
    efov.z = fov_pe2 * 1e3

    rfov = ismrmrd.xsd.fieldOfViewMm() # image fov in mm
    rfov.x = fov_ro * 1e3
    rfov.y = fov_pe1 * 1e3
    rfov.z = fov_pe2 * 1e3

    ematrix = ismrmrd.xsd.matrixSizeType() # encoding dimensions
    ematrix.x = n_enc_ro
    ematrix.y = n_enc_pe1
    ematrix.z = n_enc_pe2

    rmatrix = ismrmrd.xsd.matrixSizeType() # image dimensions
    rmatrix.x = n_enc_ro
    rmatrix.y = n_enc_pe1
    rmatrix.z = n_enc_pe2

    # set encoded and recon spaces
    escape = ismrmrd.xsd.encodingSpaceType()
    escape.matrixSize = ematrix
    escape.fieldOfView_mm = efov

    rspace = ismrmrd.xsd.encodingSpaceType()
    rspace.matrixSize = rmatrix
    rspace.fieldOfView_mm = rfov

    # encoding
    encoding = ismrmrd.xsd.encodingType()
    encoding.encodedSpace = escape
    encoding.reconSpace = rspace
    # Trajectory type required by gadgetron (not by mrpro)
    encoding.trajectory = ismrmrd.xsd.trajectoryType("cartesian")
    header.encoding.append(encoding)

    # encoding limits
    limits = ismrmrd.xsd.encodingLimitsType()

    limits.kspace_encoding_step_1 = ismrmrd.xsd.limitType()
    limits.kspace_encoding_step_1.minimum = 0
    limits.kspace_encoding_step_1.maximum = n_enc_pe1-1
    limits.kspace_encoding_step_1.center = int(n_enc_pe1 / 2)

    limits.kspace_encoding_step_2 = ismrmrd.xsd.limitType()
    limits.kspace_encoding_step_2.minimum = 0
    limits.kspace_encoding_step_2.maximum = n_enc_pe2-1
    limits.kspace_encoding_step_2.center = int(n_enc_pe2 / 2)

    encoding.encodingLimits = limits

    return (seq, header)

def sort_kspace(raw_data: np.ndarray, seq: pp.Sequence) -> np.ndarray:
    """
    Sort acquired k-space lines.

    Parameters
    ----------
    kspace
        Acquired k-space data in the format (averages, coils, pe, ro)
    trajectory
        k-Space trajectory returned by TSE constructor with dimension (pe, 2)
    dim
        dimensions of kspace
    """
    n_avg, n_coil, _, _ = raw_data.shape
    enc_dim = seq.get_definition("enc_dim")
    ksp = np.zeros((n_avg, n_coil, enc_dim[2], enc_dim[1], enc_dim[0]), dtype=complex)

    # Get k-space sorting from sequence labels
    labels = seq.evaluate_labels(evolution="adc")

    for idx, (pe_1, pe_2) in enumerate(zip(labels["LIN"], labels["PAR"])):
        ksp[..., pe_2, pe_1, :] = raw_data[:, :, idx, :]

    return ksp

# %%
