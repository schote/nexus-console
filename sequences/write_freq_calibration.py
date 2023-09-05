# %%
import numpy as np
from pypulseq.make_adc import make_adc
from pypulseq.make_delay import make_delay
from pypulseq.Sequence.sequence import Sequence
import matplotlib.pyplot as plt
from pypulseq.make_sinc_pulse import make_sinc_pulse
from pypulseq.opts import Opts
from console.pulseq_interpreter.sequence_provider import SequenceProvider


def get_frequency_calibration_sequence(
    center_freq: float = 2.048e6, 
    span: float = 50e3,
    tr: float = 5,
    rf_bandwidth: float = 50e3
    ):

    # Define system
    system = Opts(
        rf_ringdown_time=100e-6,    # Time delay at the beginning of an RF event
        rf_dead_time=100e-6,        # time delay at the end of RF event
        adc_dead_time=100e-6,       # time delay at the beginning of ADC event
    )
    system.B0 = center_freq / system.gamma

    seq = Sequence(system=system)
    seq.set_definition('Name', 'freq_adjust')

    # Determine number of RF excitations and frequency offset values
    n_excitations = 2 * int(span / (rf_bandwidth/2)) - 1
    max_frequency = span - rf_bandwidth / 2
    freq_offsets = np.linspace(-max_frequency, max_frequency, num=n_excitations)
    
    adc = make_adc(
        num_samples=1000,   # 5k samples
        duration=4e-3,      # ADC duration of 4 ms 
        system=system, 
    )
    
    for offset in freq_offsets:
        rf_block = make_sinc_pulse(
            flip_angle=np.pi/2,     # 90° RF pulse
            duration=200e-6,        # 200 us pulse duration
            time_bw_product=10,     # 10/200e-6 = 50 kHz
            apodization=0.5,
            freq_offset=offset,        
            phase_offset=np.pi/2,
            system=system,
        )
        # rf_block = make_block_pulse(
        #     flip_angle=np.pi/2,
        #     duration=200e-6,
        #     bandwidth=rf_bandwidth,
        #     freq_offset=offset,
        #     system=system
        # )
        seq.add_block(rf_block)
        seq.add_block(adc)
        seq.add_block(make_delay(tr))

        check_passed, err = seq.check_timing()

        if not check_passed:
            raise RuntimeError("Sequence timing check failed: ", err)

    return seq


# %%
# Check sequence timing and plot
span = 100e3
seq = get_frequency_calibration_sequence(rf_bandwidth=50e3, tr=10e-6, span=span)
seq.plot(time_disp='us')
seq.write('./export/freq_adjust.seq')

# %%
# Plot spectrum

offsets = []
spectra = []

fig, ax = plt.subplots(1, 1)

for k in list(seq.block_events.keys()):
    if (rf_block := seq.get_block(k).rf) is not None:
        offsets.append(rf_block.freq_offset)
        spectra.append(np.fft.ifftshift(np.fft.fft(np.fft.fftshift(rf_block.signal), norm="ortho")))
        
        # Determine frequency axis
        kmax = 0.5 * (1/(rf_block.t[1]-rf_block.t[0]))
        freq = np.linspace(-kmax, kmax, len(spectra[-1])) + offsets[-1]
        
        # Plot pulse magnitude over frequency
        ax.plot(freq/1e3, np.abs(spectra[-1]), label=f"{offsets[-1]/1e3} kHz")
        

ax.set_xlim((-150, 150))
ax.set_ylabel("Magnitude in a.u.")
ax.set_xlabel("Frequency in kHz")
ax.legend()


# %%
