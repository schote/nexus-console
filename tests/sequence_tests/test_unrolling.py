from console.utilities import sequences
from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from tests.config import seq_provider


def test_se_sequence(seq_provider):

    seq = sequences.se_spectrum.constructor()
    seq_provider.from_pypulseq(seq)
    unrolled_seq: UnrolledSequence = seq_provider.unroll_sequence(larmor_freq=2e6)

    assert unrolled_seq.duration == seq.duration()[0]


