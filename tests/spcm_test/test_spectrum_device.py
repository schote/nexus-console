"""Test spectrum devices without spectrum driver."""
import pytest

import console.spcm_control.abstract_device as device


@pytest.mark.skipif(device._driver_error is None, reason="Spectrum driver is installed.")
def test_connect_without_driver():
    """Without a driver, the devices must be importable and connecting raises a driver error."""
    from console.spcm_control.rx_device import RxCard  # noqa: F401
    from console.spcm_control.tx_device import TxCard  # noqa: F401

    class DummyDevice(device.SpectrumDevice):
        def setup_card(self) -> None: ...
        def start_operation(self) -> None: ...
        def stop_operation(self) -> None: ...

    with pytest.raises(device.SpectrumDriverError):
        DummyDevice(path="/dev/spcm0", log=None).connect()
