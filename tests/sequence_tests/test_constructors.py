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


@pytest.mark.parametrize("etl", [1, 7])
@pytest.mark.parametrize("dim", [sequences.Dimensions(64, 32, 1), sequences.Dimensions(64, 32, 32)])
@pytest.mark.parametrize("te", [20e-3])
def test_tse_3d(etl, dim, te):
    """Test 3D TSE imaging sequence constructor."""
    seq_io, acq_pos_io, n_enc_io = sequences.tse_3d.constructor(
        n_enc=dim,
        etl=etl,
        echo_time=te,
        trajectory=sequences.tse_3d.Trajectory.INOUT
    )
    seq_lin, acq_pos_lin, n_enc_lin = sequences.tse_3d.constructor(
        n_enc=dim,
        etl=etl,
        echo_time=te,
        trajectory=sequences.tse_3d.Trajectory.LINEAR
    )
    # Sequence timing checks
    assert seq_io.check_timing()[0]
    assert seq_lin.check_timing()[0]
    # acquisition positions must be different
    assert any([(p_io != p_lin).any() for p_io, p_lin in zip(acq_pos_io, acq_pos_lin)])
    # encoding dimensions must be equal
    assert n_enc_io == n_enc_lin


def test_fid_tx_calibration():
    """Test free induction decay (FID) transmit calibration sequence constructor."""
    seq, _ = sequences.fid_tx_adjust.constructor()
    assert seq.check_timing()[0]


def test_se_tx_calibration():
    """Test spin echo (SE) transmit calibration sequence constructor."""
    seq, _ = sequences.se_tx_adjust.constructor()
    assert seq.check_timing()[0]
