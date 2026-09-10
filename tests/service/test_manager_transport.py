"""Tests for the unix domain socket transport of the acquisition manager."""
import socket
from pathlib import Path

import pytest

from console import NexusNotRunningError, NexusServiceError
from console.service.acquisition_manager import AcquisitionControlManager
from console.service.authkey import generate_authkey
from console.service.paths import socket_path
from console.service.start_manager import ensure_socket_free


class DummyAcquisitionControl:
    """Stand-in for the acquisition control, no measurement hardware involved."""

    def echo(self, value: str) -> str:
        """Return the given value."""
        return value


def _dummy_acquisition_control() -> DummyAcquisitionControl:
    """Create the dummy acquisition control served by the test service."""
    return DummyAcquisitionControl()


@pytest.fixture()
def dummy_service(runtime_dir: Path):
    """Run a manager server with a dummy acquisition control on the runtime socket."""
    generate_authkey()
    server = AcquisitionControlManager(callable_acq_control=_dummy_acquisition_control)
    server.start()
    yield server
    server.shutdown()


def test_client_connects_without_arguments(dummy_service) -> None:
    """A client constructed with no arguments connects to the running service."""
    with AcquisitionControlManager() as manager:
        assert manager.acquisition.echo("nexus") == "nexus"


def test_service_uses_unix_socket(dummy_service, runtime_dir: Path) -> None:
    """The service listens on a unix domain socket, not on a TCP port."""
    assert dummy_service.address == str(socket_path())
    assert socket_path().is_socket()


def test_client_without_authkey(runtime_dir: Path) -> None:
    """Constructing a client without a running service reports the service state."""
    with pytest.raises(NexusNotRunningError, match="systemctl start nexus"):
        AcquisitionControlManager()


def test_client_without_service(runtime_dir: Path) -> None:
    """Entering the context without a listening service reports the service state."""
    generate_authkey()
    manager = AcquisitionControlManager()

    with pytest.raises(NexusNotRunningError, match="systemctl start nexus"):
        manager.__enter__()


def test_stale_socket_is_removed(runtime_dir: Path) -> None:
    """A socket file without a listener behind it is a leftover and gets removed."""
    address = socket_path()
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(address))
    stale.close()
    assert address.exists()

    ensure_socket_free(address)

    assert not address.exists()


def test_live_socket_aborts_startup(runtime_dir: Path) -> None:
    """A socket with a live service behind it must not be removed."""
    address = socket_path()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(1)

    try:
        with pytest.raises(NexusServiceError, match="already running"):
            ensure_socket_free(address)
        assert address.exists()
    finally:
        listener.close()


def test_missing_socket_is_accepted(runtime_dir: Path) -> None:
    """Without a socket file there is nothing to clean up."""
    ensure_socket_free(socket_path())

    assert not socket_path().exists()
