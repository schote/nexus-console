"""Constructor for spin-echo-based frequency calibration sequence."""
from math import pi

import numpy as np
import pypulseq as pp

# Definition of constants
RF_DURATION = 400e-6
ADC_DURATION = 4e-3

# Define system
system = pp.Opts(
    rf_ringdown_time=100e-6,  # Time delay at the beginning of an RF event
    rf_dead_time=100e-6,  # time delay at the end of RF event
    adc_dead_time=200e-6,  # time delay at the beginning of ADC event
)


def constructor(
    freq_span: float = 100e3, coil_bandwidth: float = 20e3, tr: float = 250e-3, te: float = 12e-3
) -> (pp.Sequence, np.ndarray):
    """Construct frequency adjust sequence.

    Parameters
    ----------
    f0_estimate, optional
        Estimated larmorfrequency in Hz, by default 2.035e6
    freq_span, optional
        Defines the search space in Hz: ``[f0 - freq_span, f0 + freq_span]``, by default 100e3
    coil_bandwidth, optional
        Bandwidth of receive coil in Hz, by default 20e3
    tr, optional
        Repetition time in s, by default 1000
    te, optional
        Echo time in s, by default 12e-3

    Returns
    -------
        ``Sequence`` instance and frequency offsets (f0 offsets)

    Raises
    ------
    RuntimeError
        Sequence timing failed
    """

    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "freq_adjust")

    # Determine number of RF excitations and frequency offset values
    n_excitations = 2 * int(freq_span / (coil_bandwidth / 2)) - 1
    max_frequency = freq_span - coil_bandwidth / 2
    freq_offsets = np.linspace(-max_frequency, max_frequency, num=n_excitations)

    adc = pp.make_adc(
        num_samples=1000,  # Is not taken into account atm
        duration=ADC_DURATION,
        system=system,
    )

    for offset in freq_offsets:
        rf_90 = pp.make_sinc_pulse(
            flip_angle=pi / 2,
            system=system,
            duration=RF_DURATION,
            apodization=0.5,
            freq_offset=offset,
        )

        rf_180 = pp.make_sinc_pulse(
            flip_angle=pi,  # twice the flip angle => 180°
            system=system,
            duration=RF_DURATION,
            apodization=0.5,
            freq_offset=offset,
        )

        te_delay_1 = pp.make_delay(te / 2 - RF_DURATION)
        te_delay_2 = pp.make_delay(te / 2 - RF_DURATION / 2 - ADC_DURATION / 2)

        seq.add_block(rf_90)
        seq.add_block(te_delay_1)
        seq.add_block(rf_180)
        seq.add_block(te_delay_2)
        seq.add_block(adc)
        seq.add_block(pp.make_delay(tr))

        # Check sequence timing in each iteration
        check_passed, err = seq.check_timing()
        if not check_passed:
            raise RuntimeError("Sequence timing check failed: ", err)

    return seq, freq_offsets
