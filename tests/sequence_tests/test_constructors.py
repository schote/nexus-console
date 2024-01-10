"""Test sequence constructors contained in the package."""
import pytest
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


@pytest.mark.parametrize("etl", [1, 7])
@pytest.mark.parametrize("dim", [sequences.Dimensions(64, 32, 1), sequences.Dimensions(64, 32, 32)])
@pytest.mark.parametrize("te", [40e-3, 60e-3])
def test_tse_3d(etl, dim, te):
    """Test 2D TSE imaging sequence constructor."""
    seq, _ = sequences.tse_3d.constructor(n_enc=dim, etl=etl, echo_time=te)
    assert seq.check_timing()[0] == True



def test_fid_tx_calibration():
    """Test free induction decay (FID) transmit calibration sequence constructor."""
    seq, _ = sequences.fid_tx_adjust.constructor()
    assert seq.check_timing()[0] == True



def test_se_tx_calibration():
    """Test spin echo (SE) transmit calibration sequence constructor."""
    seq, _ = sequences.se_tx_adjust.constructor()
    assert seq.check_timing()[0] == True

