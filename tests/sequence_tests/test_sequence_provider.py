"""Testing of sequence unrolling function."""
import tempfile
from pathlib import Path

from console.interfaces.unrolled_sequence import UnrolledSequence


def test_unrolling(seq_provider, test_sequence, acquisition_parameter):
    """Test unrolled sequence plot."""
    assert test_sequence.check_timing()[0]

    seq_provider.from_pypulseq(test_sequence)
    unrolled_seq: UnrolledSequence = seq_provider.unroll_sequence(acquisition_parameter)
    assert unrolled_seq.duration == test_sequence.duration()[0]


def test_slicing(seq_provider, test_sequence):
    """Test if sequence can be generated from sequence provider."""
    seq_provider.from_pypulseq(test_sequence)
    seq_sliced = seq_provider.to_pypulseq()

    for key, value in vars(test_sequence).items():
        assert hasattr(seq_sliced, key)
        assert getattr(seq_sliced, key) == value

    assert seq_sliced.duration()[0] == test_sequence.duration()[0]

    # Save sequences and compare file content
    tmp_dir = Path(tempfile.mkdtemp())
    sliced_file = tmp_dir / "sliced.seq"
    reference_file = tmp_dir / "reference.seq"

    seq_sliced.write(sliced_file)
    test_sequence.write(reference_file)

    with open(sliced_file, "r") as fh_sliced, open(reference_file, "r") as fh_ref:
        content_sliced = fh_sliced.read()
        content_ref = fh_ref.read()
    assert content_sliced == content_ref
