"""Testing plot function for unrolled sequences."""
import matplotlib as mpl
import numpy as np
from pypulseq import Sequence

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.plot import plot_unrolled_sequence

NUM_SUBPLOTS = 5

def test_unrolled_sequence_plot(
    seq_provider: SequenceProvider,
    test_sequence: Sequence,
    acquisition_parameter: AcquisitionParameter,
) -> None:
    """Test unrolled sequence plot."""
    assert test_sequence.check_timing()[0]

    seq_provider.from_pypulseq(test_sequence)
    unrolled_seq: UnrolledSequence = seq_provider.unroll_sequence(acquisition_parameter)

    fig, ax = plot_unrolled_sequence(unrolled_seq)
    assert isinstance(fig, mpl.figure.Figure)
    assert isinstance(ax, np.ndarray)
    assert len(ax) == NUM_SUBPLOTS
