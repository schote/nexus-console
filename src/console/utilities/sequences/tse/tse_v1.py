"""Constructor for 3D TSE Imaging sequence."""
# %%
from math import pi
import pypulseq as pp
from console.spcm_control.interface_acquisition_parameter import Dimensions
import numpy as np
import matplotlib.pyplot as plt

# %%
GRAD_RISE_TIME = 200e-6

# Define system
system = pp.Opts(
    rf_ringdown_time=100e-6,    # Time delay at the beginning of an RF event
    rf_dead_time=100e-6,        # time delay at the end of RF event, SETS RF DELAY!
    adc_dead_time=200e-6,       # time delay at the beginning of ADC event
)

def constructor(
    echo_time: float = 15e-3,
    repetition_time: float = 600e-3,
    etl: int = 7,
    rf_duration: float = 400e-6,
    ro_bandwidth: float = 20e3,
    fov: Dimensions = Dimensions(x=220e-3, y=220e-3, z=225e-3),
    n_enc: Dimensions = Dimensions(x=70, y=70, z=49),
) -> tuple[pp.Sequence, tuple[np.ndarray]]:
    """Constructor for 3D TSE imaging sequence.

    The k-space trajectory is constructed the following way:
    Phase encoding dimension 1 (PE1)
        In-out trajectory starting at the negative and going through zero to the positive end.
        This trajectory remains unchanged within the combination of echo trains.
    Phase encoding dimension 2 (PE2)
        Starting at the k-space center this trajectory goes to the positive and negative end in an
        alternating pattern. The PE2 steps are rotated to cover all combinations within one 
        echo train. For list rotation a lambda function is used, see example below.

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

# # Fixed parameters for debugging
# echo_time: float = 15e-3
# repetition_time: float = 600e-3
# etl: int = 5
# rf_duration: float = 400e-6
# ro_bandwidth: float = 20e3
# fov: Dimensions = Dimensions(x=220e-3, y=220e-3, z=225e-3)
# n_enc: Dimensions = Dimensions(x=60, y=60, z=25)

    # Check dimensions: Enforce that y and z encoding dimensions are multiples of the etl
    if not n_enc.y % etl == 0:
        raise ValueError("Invalid combination: PE encoding dimension y must be a multiple of the etl")
    if not n_enc.z % etl == 0:
        raise ValueError("Invalid combination: PE encoding dimension z must be a multiple of the etl")


    seq = pp.Sequence(system)
    seq.set_definition("Name", "3d_tse_v1")

    # Definition of RF pulses
    rf_90 = pp.make_sinc_pulse(system=system, flip_angle=pi/2, duration=rf_duration, apodization=0.5, use="excitation")
    rf_180 = pp.make_sinc_pulse(system=system, flip_angle=pi, duration=rf_duration, apodization=0.5, use="refocusing")

    # ADC duration
    adc_duration = n_enc.x / ro_bandwidth

    # Spacing of RF pulses (center to center)
    tau = echo_time / 2

    # Delay between excitation and first refoccusing pulse
    delay_refocus_1 = tau - rf_duration

    # Define readout gradient and prewinder
    grad_ro = pp.make_trapezoid(
        channel='x', 
        system=system, 
        flat_area=n_enc.x / fov.x,
        flat_time=adc_duration,
        rise_time=GRAD_RISE_TIME
    )
    grad_ro_pre = pp.make_trapezoid(
        channel='x', 
        system=system, 
        area=grad_ro.area / 2, 
        duration=delay_refocus_1,
        rise_time=GRAD_RISE_TIME
    )

    # Define adc event
    adc = pp.make_adc(
        system=system,
        num_samples=1000,  # Is not taken into account atm
        duration=adc_duration,
    )

    # Calculate available space for phase encoding gradients
    # In case ringdown time and dead time of RF vary, pe_space_1 and pe_space_2 are different
    pe_space_1 = (tau - rf_duration - pp.calc_duration(grad_ro)) / 2 - rf_90.ringdown_time
    pe_space_2 = (tau - rf_duration - pp.calc_duration(grad_ro)) / 2 - rf_180.dead_time

    # Define delays
    tau_1_delay = tau - rf_duration - rf_90.ringdown_time - rf_180.dead_time - pp.calc_duration(grad_ro_pre)
    tr_delay = repetition_time - pe_space_2 - adc_duration / 2

    # >> Phase encoding 1
    # Calculate maximum amplitude
    pe_1_amplitude = n_enc.y / fov.y

    pe_1_steps = (np.arange(n_enc.y) - int(n_enc.y / 2)) * pe_1_amplitude / n_enc.y
    num_pe_1_trains = int(n_enc.y / etl)
    pe_1_trains = [pe_1_steps[k::num_pe_1_trains] for k in range(num_pe_1_trains)]

    # >> Phase encoding 2
    pe_2_amplitude = n_enc.z / fov.z
    # Order phase encoding steps
    pe_2_steps = (np.arange(n_enc.z) - int(n_enc.z / 2)) * pe_2_amplitude / n_enc.z
    # Get step size of phase encoding 2
    shift = 0.5 * np.abs(pe_2_steps[1] - pe_2_steps[0])
    # Get sorted arguments of shifted magnitudes:
    # [-2, -1, 0, 1, 2] => abs([-2.25, -1.25, -0.25, 0.75, 1.75]) = [2.25, 1.25, 0.25, 0.75, 1.75]
    # Sorted indices: [2, 3, 1, 4, 0] => [0, 1, -1, 2, -2]
    order_index = np.argsort(np.abs(pe_2_steps - shift))
    pe_2_steps_ordered = [pe_2_steps[k] for k in order_index]
    # Construct list of lists for echo trains
    num_pe_2_trains = int(np.ceil(n_enc.z / etl))
    pe_2_trains = [pe_2_steps_ordered[k::num_pe_2_trains] for k in range(num_pe_2_trains)]


    # Construct the final sequence
    # Helper lambda functions to construct PE gradient and rotate a list object
    pe_grad = lambda channel, area, duration: pp.make_trapezoid(
        channel=channel, area=area, duration=duration, system=system, rise_time=GRAD_RISE_TIME
    )
    rotate_list = lambda data, k: data[k:] + data[:k]

    ro_counter = 0
    pe_traj_idx = np.zeros((2, n_enc.y*n_enc.z))
    pe_traj_mom = np.zeros((2, n_enc.y*n_enc.z))

    for pe_2_train in pe_2_trains:
        for pe_1_train in pe_1_trains:
            for tau_k in range(etl):
                # Outer echo-train loop to cover all combinations of PE1 and PE2
                # This is achieved by rotating PE2 gradient moments
                pe_2_blocks = rotate_list(pe_2_train, tau_k)

                # Add RF excitation for the echo train
                seq.add_block(rf_90)
                seq.add_block(grad_ro_pre)
                seq.add_block(tau_1_delay)
                seq.add_block(rf_180)

                for tau_j in range(etl):
                    # Inner echo-train loop which adds all the events of the train to the sequence
                    # Add phase encoding
                    seq.add_block(
                        pe_grad(channel="y", area=pe_1_train[tau_j], duration=pe_space_1),
                        pe_grad(channel="z", area=pe_2_blocks[tau_j], duration=pe_space_2)
                    )

                    # Frequency encoding and adc
                    seq.add_block(grad_ro, adc)

                    # Phase encoding inverse area
                    seq.add_block(
                        pe_grad(channel="y", area=-pe_1_train[tau_j], duration=pe_space_1),
                        pe_grad(channel="z", area=-pe_2_blocks[tau_j], duration=pe_space_2)
                    )

                    # Save trajectory indices for k-space construction and gradient moments
                    pe_traj_idx[0, ro_counter] = np.where(pe_1_steps == pe_1_train[tau_j])[0][0]
                    pe_traj_idx[1, ro_counter] = np.where(pe_2_steps == pe_2_blocks[tau_j])[0][0]
                    pe_traj_mom[0, ro_counter] = pe_1_train[tau_j]
                    pe_traj_mom[1, ro_counter] = pe_2_blocks[tau_j]

                    # Increase counter, add TR if not final echo train
                    ro_counter += 1

                # Add TR after echo train
                if ro_counter < n_enc.y * n_enc.z:
                    seq.add_block(pp.make_delay(tr_delay))


    # Calculate some sequence measures
    n_total_trains = len(pe_2_trains) * len(pe_1_trains) * etl
    train_duration_tr = (seq.duration()[0] + tr_delay)  / n_total_trains
    train_duration = train_duration_tr - tr_delay

    # Add measures to sequence definition
    seq.set_definition("n_total_trains", n_total_trains)
    seq.set_definition("train_duration", train_duration)
    seq.set_definition("train_duration_tr", train_duration_tr)
    seq.set_definition("tr_delay", tr_delay)
    
    return seq, (pe_traj_idx, pe_traj_mom)

        
# %%
# > Debugging:
# Construct example sequence using the default parameter
# encoding_dim = Dimensions(x=100, y=14, z=7)
# etl = 7
# seq, traj = constructor(n_enc=encoding_dim, etl=etl, repetition_time=50e-3)

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

# %%
