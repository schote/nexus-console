"""Test sequence constructors contained in the package."""
from console.utilities import sequences


def test_se_spectrum():
    """Test spin echo spectrum constructor."""
    seq = sequences.se_spectrum.constructor(echo_time=10e-3)
    assert seq.check_timing()[0] == True


def test_se_projection():
    """Test spin echo projection constructor."""
    seq = sequences.se_projection.constructor()
    assert seq.check_timing()[0] == True



def test_tse_2d():
    """Test 2D TSE imaging sequence constructor."""
    seq = sequences.tse_2d.constructor(etl=1)[0]
    assert seq.check_timing()[0] == True



def test_fid_tx_calibration():
    """Test free induction decay (FID) transmit calibration sequence constructor."""
    seq, _ = sequences.fid_tx_adjust.constructor()
    assert seq.check_timing()[0] == True



def test_se_tx_calibration():
    """Test spin echo (SE) transmit calibration sequence constructor."""
    seq, _ = sequences.se_tx_adjust.constructor()
    assert seq.check_timing()[0] == True

