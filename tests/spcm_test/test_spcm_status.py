"""Check status descriptions."""
import console.spcm_control.spcm.status as status


def test_status_registers():
    """Test content of status registers."""
    for key, value in status.status_reg.items():
        assert isinstance(key, int)
        assert isinstance(value, str)
    for key, value in status.status_reg_desc.items():
        assert isinstance(key, int)
        assert isinstance(value, str)
