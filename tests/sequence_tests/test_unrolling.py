"""Testing of sequence unrolling function."""
import matplotlib
import numpy as np

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter


def test_sequence_provider(seq_provider, test_sequence):
    """Test unrolled sequence plot."""
    assert test_sequence.check_timing()[0]

    seq_provider.from_pypulseq(test_sequence)
    params = AcquisitionParameter(larmor_frequency=2e6)
    unrolled_seq: UnrolledSequence = seq_provider.unroll_sequence(parameter=params)
    fig, ax = seq_provider.plot_unrolled()

    assert unrolled_seq.duration == test_sequence.duration()[0]
    assert isinstance(fig, matplotlib.figure.Figure)
    assert isinstance(ax, np.ndarray)
    assert all(isinstance(x, matplotlib.axes.Axes) for x in ax)
