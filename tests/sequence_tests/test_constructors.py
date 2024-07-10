"""Test sequence constructors contained in the package."""
import pytest
import numpy as np
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
@pytest.mark.parametrize("dim", [sequences.Dimensions(1, 50, 40), sequences.Dimensions(16, 32, 32)])
@pytest.mark.parametrize("te", [20e-3])
def test_tse_3d(etl, dim, te):
    """Test 3D TSE imaging sequence constructor."""
    seq_io, _ = sequences.tse_3d.constructor(
        n_enc=dim,
        etl=etl,
        echo_time=te,
        trajectory=sequences.tse_3d.Trajectory.INOUT
    )
    seq_lin, _ = sequences.tse_3d.constructor(
        n_enc=dim,
        etl=etl,
        echo_time=te,
        trajectory=sequences.tse_3d.Trajectory.LINEAR
    )

    # Sequence timing checks
    assert seq_io.check_timing()[0]
    assert seq_lin.check_timing()[0]

    # acquisition positions must be different, check sequence labels
    labels_io = seq_io.evaluate_labels(evolution="adc")
    labels_lin = seq_lin.evaluate_labels(evolution="adc")
    test_lin_equal = [x != y for x, y in zip(labels_io["LIN"], labels_lin["LIN"])]
    test_par_equal = [x != y for x, y in zip(labels_io["PAR"], labels_lin["PAR"])]

    assert any(test_lin_equal[1:])  # starting point might be equal
    if 1 not in seq_io.get_definition("enc_dim"):
        assert any(test_par_equal[1:])  # starting point might be equal

    # encoding dimensions must be equal
    n_enc_io = seq_io.get_definition("enc_dim")
    n_enc_lin = seq_lin.get_definition("enc_dim")
    assert n_enc_io == n_enc_lin

    # TODO: Add checks for ismrmrd header (2nd argument returned by constructor)


def test_fid_tx_calibration():
    """Test free induction decay (FID) transmit calibration sequence constructor."""
    seq, _ = sequences.fid_tx_adjust.constructor()
    assert seq.check_timing()[0]


def test_se_tx_calibration():
    """Test spin echo (SE) transmit calibration sequence constructor."""
    seq, _ = sequences.se_tx_adjust.constructor()
    assert seq.check_timing()[0]
