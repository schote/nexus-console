"""Tests for the unix domain socket transport and authentication of the acquisition manager."""
import socket
import stat
from pathlib import Path

import pytest

from nexus_service import acquisition_manager
from nexus_service.acquisition_manager import AcquisitionControlManager, NexusNotRunningError, runtime_dir
from nexus_service.start_manager import ensure_socket_free


class DummyAcquisitionControl:
    """Stand-in for the acquisition control, no measurement hardware involved."""

    def echo(self, value: str) -> str:
        """Return the given value."""
        return value


@pytest.fixture()
def dummy_service(nexus_runtime_dir: Path):
    """Run a manager server with a dummy acquisition control on the runtime socket."""
    server = AcquisitionControlManager(callable_acq_control=DummyAcquisitionControl)
    server.start()
    yield server
    server.shutdown()


def test_client_connects_without_arguments(dummy_service) -> None:
    """A client constructed with no arguments connects to the running service."""
    with AcquisitionControlManager() as manager:
        assert manager.acquisition.echo("nexus") == "nexus"


def test_service_uses_unix_socket(dummy_service, nexus_runtime_dir: Path) -> None:
    """The service listens on a unix domain socket in the runtime directory, not on a TCP port."""
    assert dummy_service.address == str(nexus_runtime_dir / "nexus.sock")
    assert (nexus_runtime_dir / "nexus.sock").is_socket()


def test_runtime_files_permissions(dummy_service, nexus_runtime_dir: Path) -> None:
    """Every account can read the key and use the sticky runtime directory."""
    assert stat.S_IMODE((nexus_runtime_dir / "authkey").stat().st_mode) == 0o644
    assert stat.S_IMODE(nexus_runtime_dir.stat().st_mode) == 0o1777


def test_client_without_authkey(nexus_runtime_dir: Path) -> None:
    """Constructing a client without a running service reports the service state."""
    with pytest.raises(NexusNotRunningError, match="systemctl start nexus"):
        AcquisitionControlManager()


def test_client_without_service(nexus_runtime_dir: Path) -> None:
    """Entering the context without a listening service reports the service state."""
    manager = AcquisitionControlManager(authkey=b"key")

    with pytest.raises(NexusNotRunningError, match="systemctl start nexus"):
        manager.__enter__()


def test_runtime_dir_of_a_foreign_owner(nexus_runtime_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A client which does not own the directory still resolves it, as long as its permissions are right."""
    nexus_runtime_dir.mkdir(parents=True)
    nexus_runtime_dir.chmod(0o1777)

    def _deny(*args: object, **kwargs: object) -> None:
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(Path, "chmod", _deny)

    assert runtime_dir() == nexus_runtime_dir


def test_runtime_dir_with_wrong_permissions(nexus_runtime_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pre-created directory which cannot be given the right permissions is refused."""
    nexus_runtime_dir.mkdir(parents=True)
    nexus_runtime_dir.chmod(0o755)

    def _deny(*args: object, **kwargs: object) -> None:
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(Path, "chmod", _deny)

    with pytest.raises(RuntimeError, match="wrong permissions"):
        runtime_dir()


def test_system_runtime_dir_is_used_as_is(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A directory provided by systemd is used without changing its permissions."""
    system_dir = tmp_path / "run" / "nexus"
    system_dir.mkdir(parents=True)
    system_dir.chmod(0o755)
    monkeypatch.delenv("NEXUS_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(acquisition_manager, "SYSTEM_RUNTIME_DIR", system_dir)

    assert runtime_dir() == system_dir
    assert stat.S_IMODE(system_dir.stat().st_mode) == 0o755


def test_environment_overrides_system_runtime_dir(
    tmp_path: Path, nexus_runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The environment variable wins over the systemd directory, so tests stay isolated from a service."""
    system_dir = tmp_path / "run" / "nexus"
    system_dir.mkdir(parents=True)
    monkeypatch.setattr(acquisition_manager, "SYSTEM_RUNTIME_DIR", system_dir)

    assert runtime_dir() == nexus_runtime_dir


def test_missing_system_runtime_dir_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the systemd directory the temporary directory is used as before."""
    fallback = tmp_path / "tmp"
    fallback.mkdir()
    monkeypatch.delenv("NEXUS_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(acquisition_manager, "SYSTEM_RUNTIME_DIR", tmp_path / "run" / "nexus")
    monkeypatch.setattr(acquisition_manager.tempfile, "gettempdir", lambda: str(fallback))

    assert runtime_dir() == fallback / "nexus"
    assert stat.S_IMODE((fallback / "nexus").stat().st_mode) == 0o1777


def test_stale_socket_is_removed(nexus_runtime_dir: Path) -> None:
    """A socket file without a listener behind it is a leftover and gets removed."""
    address = runtime_dir() / "nexus.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(address))
    stale.close()
    assert address.exists()

    ensure_socket_free(address)

    assert not address.exists()


def test_live_socket_aborts_startup(nexus_runtime_dir: Path) -> None:
    """A socket with a live service behind it must not be removed."""
    address = runtime_dir() / "nexus.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(1)

    try:
        with pytest.raises(RuntimeError, match="already running"):
            ensure_socket_free(address)
        assert address.exists()
    finally:
        listener.close()


def test_missing_socket_is_accepted(nexus_runtime_dir: Path) -> None:
    """Without a socket file there is nothing to clean up."""
    address = runtime_dir() / "nexus.sock"

    ensure_socket_free(address)

    assert not address.exists()
