"""Test the spectrum device interface based on spcm_core, without driver and cards."""
import pytest

import console.spcm_control.abstract_device as abstract_device
from console.spcm_control.abstract_device import SpectrumDriverError, type_to_name

CARD_HANDLE = 1  # handle returned by the mocked spcm_hOpen, see conftest


@pytest.mark.parametrize(
    ("series", "version", "name"),
    [
        ("TYP_M2PEXPSERIES", 0x6546, "M2p.6546-x4"),
        ("TYP_M2PEXPSERIES", 0x5933, "M2p.5933-x4"),
        ("TYP_M4IEXPSERIES", 0x4451, "M4i.4451-x8"),
        ("TYP_M5IEXPSERIES", 0x3321, "M5i.3321-x16"),
    ],
)
def test_type_to_name(fake_spcm, series, version, name):
    """Card type codes are translated to the card name."""
    assert type_to_name(getattr(fake_spcm, series) | version) == name


@pytest.mark.usefixtures("fake_spcm")
def test_type_to_name_unknown():
    """Unknown card series is reported as unknown type."""
    assert type_to_name(0x00FF0000) == "unknown type"


def test_connect_without_driver(device, fake_spcm, monkeypatch):
    """Missing driver raises a driver error, which is a connection error, before the card is opened."""
    monkeypatch.setattr(abstract_device, "_driver_error", Exception("driver not found"))
    with pytest.raises(SpectrumDriverError, match="driver not found"):
        device.connect()
    assert issubclass(SpectrumDriverError, ConnectionError)
    fake_spcm.spcm_hOpen.assert_not_called()


def test_connect(device, fake_spcm):
    """Opened card is identified and set up."""
    fake_spcm.params[fake_spcm.SPC_PCITYP] = fake_spcm.TYP_M2PEXPSERIES | 0x6546
    assert device.connect()
    assert device.card == CARD_HANDLE
    assert device.name == "M2p.6546-x4"
    device.setup_card.assert_called_once()


def test_connect_failed(device, fake_spcm):
    """Card which cannot be opened raises a connection error."""
    fake_spcm.spcm_hOpen.return_value = 0
    with pytest.raises(ConnectionError, match="Could not connect"):
        device.connect()
    device.setup_card.assert_not_called()


@pytest.mark.parametrize("error", ["ERR_OK", "ERR_TIMEOUT"])
def test_handle_error_ignored(device, fake_spcm, error):
    """No error and timeouts do not stop the card."""
    device.handle_error(getattr(fake_spcm, error))
    fake_spcm.spcm_dwGetErrorInfo_i32.assert_not_called()
    fake_spcm.spcm_dwSetParam_i32.assert_not_called()


def test_handle_error(device, fake_spcm):
    """Errors are reported with driver text, register and value, and stop the card."""
    device.card = CARD_HANDLE
    fake_spcm.error_info = (b"Value out of range", fake_spcm.SPC_SAMPLERATE, 42)
    with pytest.raises(RuntimeError) as exc_info:
        device.handle_error(fake_spcm.ERR_VALUE)
    msg = str(exc_info.value)
    assert "Value out of range" in msg
    assert f"error {fake_spcm.ERR_VALUE}" in msg
    assert f"register {fake_spcm.SPC_SAMPLERATE}" in msg
    assert "value 42" in msg
    fake_spcm.spcm_dwSetParam_i32.assert_called_once_with(
        CARD_HANDLE, fake_spcm.SPC_M2CMD, fake_spcm.M2CMD_CARD_STOP,
    )
    device.log.critical.assert_called_once()


def test_get_status(device, fake_spcm):
    """Status value is returned and the names of the set flags are logged."""
    status = fake_spcm.M2STAT_CARD_READY | fake_spcm.M2STAT_DATA_END
    fake_spcm.params[fake_spcm.SPC_M2STATUS] = status
    assert device.get_status() == status
    flags = device.log.debug.call_args.args[1]
    assert sorted(flags) == ["M2STAT_CARD_READY", "M2STAT_DATA_END"]


def test_disconnect(device, fake_spcm):
    """Card is stopped, reset and closed on disconnect."""
    device.card = CARD_HANDLE
    device.name = "M2p.6546-x4"
    device.disconnect()
    commands = [call.args[2] for call in fake_spcm.spcm_dwSetParam_i32.call_args_list]
    assert commands == [fake_spcm.M2CMD_CARD_STOP, fake_spcm.M2CMD_CARD_RESET]
    fake_spcm.spcm_vClose.assert_called_once_with(CARD_HANDLE)
    assert device.card is None
    assert device.name is None


def test_disconnect_without_card(device, fake_spcm):
    """Disconnect without connected card does not call the driver."""
    device.disconnect()
    fake_spcm.spcm_vClose.assert_not_called()


def test_dict(device):
    """Serializable attributes are exported, ctypes values by their value."""
    device.card_type.value = 7
    attributes = device.dict()
    assert attributes["path"] == "/dev/spcm0"
    assert attributes["card_type"] == 7
    assert "log" not in attributes


@pytest.mark.skipif(abstract_device._driver_error is None, reason="Spectrum driver is installed.")
def test_devices_importable_without_driver():
    """Without a driver, the rx and tx device modules must still be importable."""
    from console.spcm_control.rx_device import RxCard  # noqa: F401
    from console.spcm_control.tx_device import TxCard  # noqa: F401
