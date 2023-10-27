# %%
from math import pi
import pypulseq as pp
from console.spcm_control.interface_acquisition_parameter import Dimensions
import numpy as np
import matplotlib.pyplot as plt


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
    n_enc: Dimensions = Dimensions(x=64, y=64, z=25),
) -> pp.Sequence:
    """Constructor for 3D TSE imaging sequence.

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
        Number of encodings steps (dimensions), by default Dimensions(x=64, y=64, z=25)

    Returns
    -------
        Pypulseq ``Sequence`` instance
    """
    
    seq = pp.Sequence(system)
    seq.set_definition("Name", "3d_tse")

    # Definition of RF pulses
    rf_90 = pp.make_sinc_pulse(system=system, flip_angle=pi / 2, duration=rf_duration, apodization=0.5, use="excitation")
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
    num_pe_2_trains = int(n_enc.z / etl)
    pe_2_trains = [pe_2_steps_ordered[k::num_pe_2_trains] for k in range(num_pe_2_trains)]

    # Construct the final sequence
    # Function which returns a phase encoding gradient for given area and channel
    def pe_grad(channel: str, area: float, duration: float):
        return pp.make_trapezoid(
            system=system,
            rise_time=GRAD_RISE_TIME,
            channel=channel,
            area=area,
            duration=duration
        )

    for pe_2_train in pe_2_trains:
        for pe_1_train in pe_1_trains:
            
            seq.add_block(rf_90)
            seq.add_block(grad_ro_pre)
            seq.add_block(tau_1_delay)
            seq.add_block(rf_180)
            
            for tau_k in range(etl):
                # Add phase encoding
                seq.add_block(
                    pe_grad(channel="y", area=pe_1_train[tau_k], duration=pe_space_1),
                    pe_grad(channel="z", area=pe_2_train[tau_k], duration=pe_space_1)
                )
                # Frequency encoding and adc
                seq.add_block(grad_ro, adc)
                # Phase encoding inverse area
                seq.add_block(
                    pe_grad(channel="y", area=-pe_1_train[tau_k], duration=pe_space_2),
                    pe_grad(channel="z", area=-pe_2_train[tau_k], duration=pe_space_2)
                )

            seq.add_block(pp.make_delay(tr_delay))
    
    
    # Calculate some sequence measures
    n_total_trains = len(pe_2_trains) * len(pe_1_trains)
    train_duration = seq.duration()[0] / n_total_trains - tr_delay
    train_duration_tr = seq.duration()[0] / n_total_trains
    
    # Add measures to sequence definition
    seq.set_definition("n_total_trains", n_total_trains)
    seq.set_definition("train_duration", train_duration)
    seq.set_definition("train_duration_tr", train_duration_tr)
    seq.set_definition("tr_delay", tr_delay)
    
    return seq

        
# %%
# construct sequence with default values
# seq: pp.Sequence = constructor()

# seq.plot(time_disp="ms")

# %%
# Plot each train in sequence
# n_total_trains = seq.definitions["n_total_trains"]
# train_duration = seq.definitions["train_duration"]
# tr_delay = seq.definitions["tr_delay"]

# k = 0
# t_offset = (train_duration + tr_delay) * k
# seq.plot(time_disp="ms", time_range=(t_offset, t_offset+0.065))
# plt.savefig(f"/home/schote01/data/tse_seq/tse_train_{str(k+1).zfill(3)}")

# for k in range(n_total_trains):
#     t_offset = (train_duration + tr_delay) * k
#     seq.plot(time_disp="ms", time_range=(t_offset, t_offset+0.065))
#     plt.savefig(f"/home/schote01/data/tse_seq/tse_train_{str(k+1).zfill(3)}")
    
# %%
# # Plot phase encoding 1
# colors = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown", "tab:pink", "tab:gray", "tab:cyan"]
# fig, ax = plt.subplots(1, 1, figsize=(6, 6))
# for k, train in enumerate(pe_1_trains):
#     c = colors[k]
#     for echo in train:
#         ax.plot([-1, 1], [echo]*2, color=c)
# ax.set_xticks([-1, 1])
# ax.set_xlabel("Readout")
# ax.set_ylabel("PE 1 Steps")

