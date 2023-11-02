"""Interface class for an unrolled sequence."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class UnrolledSequence:
    """Unrolled sequence interface.

    This interface is used to share the unrolled sequence between the
    different components like TxEngine, SequenceProvider and AcquisitionControl.
    An unrolled sequence is generated by a `SequenceProvider()` instance using the
    `unroll_sequence` function.

    Parameters
    ----------
    seq
        Replay data as int16 values in a list of numpy arrays. The sequence data already
        contains the digital adc and unblanking signals in the channels gx and gy.

    adc_gate
        ADC gate signal in binary logic where 0 corresponds to ADC gate off and 1 to ADC gate on.

    rf_unblanking
        Unblanking signal for the RF power amplifier (RFPA) in binary logic. 0 corresponds to blanking state
        and 1 to unblanking state.

    sample_count
        Total number of samples per channel.

    grad_to_volt
        The gradient waveforms in pulseq are defined in Hz/m. This factor accounts for the translation to
        mV taking into account the gpa gain and the gradient efficiency. 
        The gpa gain is given in V/A and accounts for the voltage required to generate an output of 1A.
        The gradient efficiency is given in mT/m/A and accounts for the gradient field which is generated per 1A.
        The relation is defined by 
        grad_to_volt = 1e3 / (gyro * gpa_gain * grad_efficiency), where gyro is the gyromagnetic ratio 
        defined by 42.58e6 MHz/T.

    rf_to_mvolt
        If sequence values are given as float values, they can be interpreted as output voltage [mV] directly.
        This conversion factor represents the scaling from original pulseq RF values [Hz] to card output voltage.

    dwell_time
        Dwell time of the spectrum card replay data (unrolled sequence).
        Defines the distance in time between to sample points.
        Note that this dwell time does not correlate to the larmor frequecy. Due to the sampling theorem
        `dwell_time < 1/(2*larmor_frequency)` must be satisfied. Usually a higher factor is chosen.

    larmor_frequency
        Larmor frequency of the MR scanner which defines the frequency of the RF pulse carrier signal.
    
    grad_correction
        Time correction factor for trapezoidal gradients. Adds to the flat time duration.
    
    """

    seq: list
    adc_gate: list
    rf_unblanking: list
    sample_count: int
    grad_to_volt: float
    rf_to_mvolt: float
    dwell_time: float
    larmor_frequency: float
    duration: float
    adc_count: int
    grad_correction: float
