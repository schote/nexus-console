"""Constructor for 3D TSE Imaging sequence."""
# %%
from math import pi
from types import SimpleNamespace

import numpy as np
import pypulseq as pp

from console.spcm_control.interface_acquisition_parameter import Dimensions
from console.utilities.sequences.system_settings import system

GRAD_RISE_TIME = 200e-6

default_fov = Dimensions(x=220e-3, y=220e-3, z=225e-3)
default_encoding = Dimensions(x=70, y=70, z=49)


# %%
def constructor(
    echo_time: float = 15e-3,
    repetition_time: float = 600e-3,
    etl: int = 7,
    rf_duration: float = 400e-6,
    gradient_correction: float = 510e-6,
    ro_bandwidth: float = 20e3,
    fov: Dimensions = default_fov,
    n_enc: Dimensions = default_encoding,
) -> tuple[pp.Sequence, tuple[np.ndarray]]:
    """Construct 2D TSE imaging sequence.

    The k-space trajectory is constructed the following way:
    Phase encoding dimension 1 (PE1)
        In-out trajectory starting at the negative and going through zero to the positive end.
        This trajectory remains unchanged within the combination of echo trains.

    Examples
    --------
    List rotation
    >>> rotated_list = rotate_list([1, 2, 3, 4], k=2)
    The rotation of ``[1, 2, 3, 4]`` with ``k=2`` gives ``[3, 4, 1, 2]``


    Parameters
    ----------
    echo_time, optional
        Echo time in s, by default 15e-3
    repetition_time, optional
        Repetition time (TR) in s, by default 600e-3
    etl, optional
        Echo train length as integer, by default 7
    rf_duration, optional
        RF duration in s, by default 400e-6
    ro_bandwidth, optional
        Readout bandwidth in Hz, by default 20e3
    fov, optional
        Field of view per dimension in m, by default Dimensions(x=220e-3, y=220e-3, z=225e-3)
    n_enc, optional
        Number of encodings steps (dimensions). For this version the number of phase encoding steps 1
        and to (y and z) must be multiples of the echo train length, by default Dimensions(x=70, y=70, z=49)

    Returns
    -------
        Pypulseq ``Sequence`` instance and trajectory tuple.
        The first element in the tuple describes the index ordering, the second tuple contains the gradient moments.
    """
    # Check dimensions: Enforce that y and z encoding dimensions are multiples of the etl
    if not n_enc.y % etl == 0:
        raise ValueError("Invalid combination: PE encoding dimension y must be a multiple of the etl")
    if not n_enc.z % etl == 0:
        raise ValueError("Invalid combination: PE encoding dimension z must be a multiple of the etl")

    seq = pp.Sequence(system)
    seq.set_definition("Name", "2d_tse_v1")

    # Definition of RF pulses
    rf_90 = pp.make_block_pulse(system=system, flip_angle=pi / 2, duration=rf_duration, use="excitation")
    rf_180 = pp.make_block_pulse(system=system, flip_angle=pi, duration=rf_duration, use="refocusing")

    # ADC duration
    adc_duration = n_enc.x / ro_bandwidth

    # Spacing of RF pulses (center to center)
    tau = echo_time / 2

    # Define readout gradient and prewinder
    grad_ro = pp.make_trapezoid(
        channel="x",
        system=system,
        flat_area=n_enc.x / fov.x,
        flat_time=adc_duration + gradient_correction,
        rise_time=GRAD_RISE_TIME,
    )

    grad_ro_pre = pp.make_trapezoid(
        channel="x",
        system=system,
        area=grad_ro.area / 2,
        duration=pp.calc_duration(grad_ro) / 2,
        rise_time=GRAD_RISE_TIME,
    )

    # Delay between excitation and first refoccusing pulse
    # delay_post_ro_prephaser = tau - rf_duration - pp.calc_duration(grad_ro_pre)

    # Define adc event
    adc = pp.make_adc(
        system=system,
        num_samples=1000,  # Is not taken into account atm
        duration=adc_duration,
        delay=gradient_correction + GRAD_RISE_TIME,
    )

    # Calculate available space for phase encoding gradients

    pe_duration = pp.calc_duration(grad_ro) / 2

    # In case ringdown time and dead time of RF vary, pe_space_1 and pe_space_2 are different
    # pe_space_1 = (tau - rf_duration - pp.calc_duration(grad_ro)) / 2 - rf_90.ringdown_time - pe_duration
    # pe_space_2 = (tau - rf_duration - pp.calc_duration(grad_ro)) / 2 - rf_180.dead_time - pe_duration

    pe_space_1 = (
        tau
        - rf_duration / 2
        - adc_duration / 2
        - GRAD_RISE_TIME
        - gradient_correction
        - pe_duration
        - rf_90.ringdown_time
    )
    pe_space_2 = tau - rf_duration / 2 - adc_duration / 2 - GRAD_RISE_TIME - pe_duration - rf_180.ringdown_time

    # Define delays
    tau_1_delay = tau - rf_duration - rf_90.ringdown_time - rf_180.dead_time - pp.calc_duration(grad_ro_pre)
    tr_delay = repetition_time - pe_space_2 - adc_duration / 2

    # >> Phase encoding 1
    # Calculate maximum amplitude
    pe_1_amplitude = n_enc.y / fov.y

    pe_1_steps = (np.arange(n_enc.y) - int(n_enc.y / 2)) * pe_1_amplitude / n_enc.y
    num_pe_1_trains = int(n_enc.y / etl)
    pe_1_trains = [pe_1_steps[k::num_pe_1_trains] for k in range(num_pe_1_trains)]

    # Construct the final sequence
    # Helper functions to construct PE gradient and rotate a list object
    def get_pe_grad(channel: str, area: float, duration: float) -> SimpleNamespace:
        return pp.make_trapezoid(
            channel=channel,
            area=area,
            duration=duration,
            system=system,
            rise_time=GRAD_RISE_TIME,
        )

    ro_counter = 0
    pe_traj_idx = np.zeros(n_enc.y)
    pe_traj_mom = np.zeros(n_enc.y)

    for pe_1_train in pe_1_trains:
        for _ in range(etl):
            # Add RF excitation for the echo train
            seq.add_block(rf_90)
            seq.add_block(grad_ro_pre)
            seq.add_block(pp.make_delay(tau_1_delay))

            for tau_j in range(etl):
                seq.add_block(rf_180)

                # Inner echo-train loop which adds all the events of the train to the sequence
                # Add phase encoding
                seq.add_block(get_pe_grad(channel="y", area=pe_1_train[tau_j], duration=pe_duration))
                seq.add_block(pp.make_delay(pe_space_1))

                # Frequency encoding and adc
                seq.add_block(grad_ro, adc)

                seq.add_block(pp.make_delay(pe_space_2))
                # Phase encoding inverse area
                seq.add_block(get_pe_grad(channel="y", area=-pe_1_train[tau_j], duration=pe_duration))

                # Save trajectory indices for k-space construction and gradient moments
                pe_traj_idx[ro_counter] = np.where(pe_1_steps == pe_1_train[tau_j])[0][0]
                pe_traj_mom[ro_counter] = pe_1_train[tau_j]

                # Increase counter, add TR if not final echo train
                ro_counter += 1

            # Add TR after echo train
            if ro_counter < n_enc.y:
                seq.add_block(pp.make_delay(tr_delay))

    # Calculate some sequence measures
    n_total_trains = len(pe_1_trains) * etl
    train_duration_tr = (seq.duration()[0] + tr_delay) / n_total_trains
    train_duration = train_duration_tr - tr_delay

    # Add measures to sequence definition
    seq.set_definition("n_total_trains", n_total_trains)
    seq.set_definition("train_duration", train_duration)
    seq.set_definition("train_duration_tr", train_duration_tr)
    seq.set_definition("tr_delay", tr_delay)

    # Check sequence timing in each iteration
    check_passed, err = seq.check_timing()
    if not check_passed:
        raise RuntimeError("Sequence timing check failed: ", err)

    return seq, (pe_traj_idx, pe_traj_mom)


# %%
# > Debugging:
# Construct example sequence using the default parameter
# encoding_dim = Dimensions(x=64, y=64, z=0)
# etl = 1
# seq, traj = constructor(
#     echo_time=20e-3,
#     repetition_time=300e-3,
#     etl=etl,
#     gradient_correction=510e-6,
#     rf_duration=200e-6,
#     ro_bandwidth=20e3,
#     fov=Dimensions(x=220e-3, y=220e-3, z=225e-3),
#     n_enc=encoding_dim
# )

# seq.plot(time_range=(0, 0.032))

# %%
# Plot sequence and k-space
# seq.plot(time_disp="ms")

# grad_moments = traj[1]
# ksp_pos_pe1 = traj[0][0] - int(encoding_dim.y / 2)
# ksp_pos_pe2 = traj[0][1] - int(encoding_dim.z / 2)

# fig, ax = plt.subplots(1, 2, figsize=(16, 8))
# ax[0].plot(grad_moments[0], grad_moments[1], color="b", linewidth=0.5)
# ax[0].scatter(grad_moments[0], grad_moments[1], marker="x", color="r")
# ax[0].set_xlabel("Gradient moment [kHz/m], PE 1 (Y)")
# ax[0].set_ylabel("Gradient moment [kHz/m], PE 2 (Z)")

# ax[1].scatter(ksp_pos_pe1, ksp_pos_pe2, s=10, color="r")
# ax[1].set_xlabel("ky")
# ax[1].set_ylabel("kz")


# %%
# Plot echo-train k from sequence
# n_total_trains = seq.definitions["n_total_trains"]
# train_duration = seq.definitions["train_duration"]
# tr_delay = seq.definitions["tr_delay"]

# # indices = [0, 1, 2, 3, 4, 5, 6]
# indices = [0]

# for k in indices:
#     t_offset = (train_duration + tr_delay) * k
#     seq.plot(time_disp="ms", time_range=(t_offset, t_offset+train_duration*1.05))
