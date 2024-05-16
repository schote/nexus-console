"""Test sequence constructors contained in the package."""
import pytest

from console.utilities import sequences


@pytest.mark.parametrize("use_sinc", [True, False])
def test_se_spectrum(use_sinc: bool):
    """Test spin echo spectrum constructor."""
    seq = sequences.se_spectrum.constructor(use_sinc=use_sinc)
    assert seq.check_timing()[0]


@pytest.mark.parametrize("use_sinc", [True, False])
@pytest.mark.parametrize("channel", ["x", "y", "z"])
def test_se_projection(channel: str, use_sinc: bool):
    """Test spin echo projection constructor."""
    seq = sequences.se_projection.constructor(channel=channel, use_sinc=use_sinc)
    assert seq.check_timing()[0]


def test_se_spectrum_dl():
    """Test spin echo spectrum constructor with 2nd ADC window."""
    seq = sequences.se_spectrum_dl.constructor()
    assert seq.check_timing()[0]


def test_t2_relaxation():
    """Test sequence to measure T2."""
    seq, _ = sequences.t2_relaxation.constructor()
    assert seq.check_timing()[0]


def test_tse_2d():
    """Test 2D TSE imaging sequence constructor."""
    seq = sequences.tse_2d.constructor(etl=1)[0]
    assert seq.check_timing()[0]


@pytest.mark.parametrize("etl", [1, 7])
@pytest.mark.parametrize("dim", [sequences.Dimensions(64, 32, 1), sequences.Dimensions(64, 32, 32)])
@pytest.mark.parametrize("te", [40e-3, 60e-3])
def test_tse_3d(etl, dim, te):
    """Test 2D TSE imaging sequence constructor."""
    seq, _ = sequences.tse_3d.constructor(n_enc=dim, etl=etl, echo_time=te)
    assert seq.check_timing()[0]


def test_fid_tx_calibration():
    """Test free induction decay (FID) transmit calibration sequence constructor."""
    seq, _ = sequences.fid_tx_adjust.constructor()
    assert seq.check_timing()[0]


def test_se_tx_calibration():
    """Test spin echo (SE) transmit calibration sequence constructor."""
    seq, _ = sequences.se_tx_adjust.constructor()
    assert seq.check_timing()[0]
