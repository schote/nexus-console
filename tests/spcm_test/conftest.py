"""Fixtures to test the spectrum devices without driver and cards."""
import ctypes
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import console.spcm_control.abstract_device as abstract_device

CARD_HANDLE = 1


def load_spcm_core_module(name: str) -> ModuleType:
    """Load a constants module of spcm_core without executing the package init, which requires the driver."""
    package_spec = importlib.util.find_spec("spcm_core")
    assert package_spec is not None
    assert package_spec.submodule_search_locations
    path = Path(next(iter(package_spec.submodule_search_locations))) / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_test_spcm_core_{name}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONSTANTS = {
    key: val
    for module in (load_spcm_core_module("regs"), load_spcm_core_module("spcerr"))
    for key, val in vars(module).items()
    if not key.startswith("_")
}


class DummyDevice(abstract_device.SpectrumDevice):
    """Minimal spectrum device implementing the abstract methods."""

    def setup_card(self) -> None:
        """Do nothing, setup is recorded by mock in tests."""

    def start_operation(self) -> None:
        """Do nothing."""

    def stop_operation(self) -> None:
        """Do nothing."""


@pytest.fixture
def fake_spcm(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Replace spcm_core in the abstract device by real constants and mocked driver functions.

    Registers read by spcm_dwGetParam_i32 are taken from ``fake.params``,
    the error info returned by spcm_dwGetErrorInfo_i32 from ``fake.error_info``.
    The real driver is never called, also on systems with installed driver.
    """
    fake = SimpleNamespace(**CONSTANTS, int32=ctypes.c_int32, uint32=ctypes.c_uint32)
    fake.params = {}
    fake.error_info = (b"Driver error text", 0, 0)

    def get_param(_card, register, ref):
        ref._obj.value = fake.params.get(register, 0)
        return fake.ERR_OK

    def get_error_info(_card, reg_ref, val_ref, text):
        text.value, reg_ref._obj.value, val_ref._obj.value = fake.error_info
        return fake.ERR_REG

    fake.spcm_hOpen = Mock(return_value=CARD_HANDLE)
    fake.spcm_vClose = Mock()
    fake.spcm_dwGetParam_i32 = Mock(side_effect=get_param)
    fake.spcm_dwSetParam_i32 = Mock(return_value=fake.ERR_OK)
    fake.spcm_dwGetErrorInfo_i32 = Mock(side_effect=get_error_info)

    monkeypatch.setattr(abstract_device, "spcm", fake, raising=False)
    monkeypatch.setattr(abstract_device, "_driver_error", None)
    return fake


@pytest.fixture
def device(fake_spcm: SimpleNamespace) -> DummyDevice:  # noqa: ARG001, fixture replaces the driver
    """Spectrum device with mocked driver and logger."""
    dev = DummyDevice(path="/dev/spcm0", log=MagicMock())
    dev.setup_card = Mock()  # type: ignore[method-assign]
    return dev
