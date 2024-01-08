from console.utilities import sequences


def test_se_spectrum():
    seq = sequences.se_spectrum.constructor(echo_time=10e-3)
    assert seq.check_timing()[0] == True


def test_se_projection():
    seq = sequences.se_projection.constructor()
    assert seq.check_timing()[0] == True



def test_tse_2d():
    seq, _ = sequences.tse_2d.constructor(etl=1)
    assert seq.check_timing()[0] == True



def test_fid_tx_calibration():
    seq, _ = sequences.fid_tx_adjust.constructor()
    assert seq.check_timing()[0] == True



def test_se_tx_calibration():
    seq, _ = sequences.se_tx_adjust.constructor()
    assert seq.check_timing()[0] == True

