import pytest

from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.utilities.sequences.system_settings import system


@pytest.fixture()
def seq_provider():
    return SequenceProvider(
        gradient_efficiency=[.4, .4, .4],
        gpa_gain=[1.0, 1.0, 1.0],
        output_limits=[200, 6000, 6000, 6000],
        spcm_dwell_time=5e-8,
        rf_to_mvolt=5e-3,
        system=system
    )
