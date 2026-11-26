"""Tests for the unix domain socket transport and authentication of the acquisition manager."""
import os
import stat
import subprocess
import sys
from multiprocessing import AuthenticationError
from multiprocessing.connection import Listener
from pathlib import Path

import pytest

from nexus_service import acquisition_manager
from nexus_service.acquisition_manager import (
    AcquisitionControlManager,
    NexusNotRunningError,
    runtime_dir,
    service_address,
)
from nexus_service.start_manager import claim_runtime_dir, release_runtime_dir

# Unix domain sockets, POSIX permissions and systemd do not exist on Windows
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")


class DummyAcquisitionControl:
    """Stand-in for the acquisition control, no measurement hardware involved."""

    def get_progress(self) -> int:
        """Return a fixed progress, the method is part of the API exposed to clients."""
        return 42

    def close(self) -> None:
        """Owned by the service, must not be exposed to clients."""


@pytest.fixture()
def dummy_service(nexus_runtime_dir: Path):
    """Run a manager server with a dummy acquisition control on the runtime socket."""
    claim_runtime_dir(nexus_runtime_dir, service_address())
    server = AcquisitionControlManager(callable_acq_control=DummyAcquisitionControl)
    server.start()
    yield server
    server.shutdown()  # the server process removes the socket when it exits
    server.key_file.unlink()
    release_runtime_dir(nexus_runtime_dir)


def _owned_by_another_account(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Let ``path`` appear to belong to another account, creating a file of another account requires root."""
    lstat = Path.lstat

    def _lstat(self: Path) -> os.stat_result:
        result = lstat(self)
        if self != path:
            return result
        return os.stat_result((*result[:4], os.getuid() + 1, *result[5:]))  # index 4 is the owner

    monkeypatch.setattr(Path, "lstat", _lstat)


@pytest.mark.usefixtures("dummy_service")
def test_client_connects_without_arguments() -> None:
    """A client constructed with no arguments connects to the running service."""
    with AcquisitionControlManager() as manager:
        assert manager.acquisition.get_progress() == 42


@pytest.mark.usefixtures("dummy_service")
def test_close_is_not_exposed() -> None:
    """Clients cannot disconnect the cards, shutdown is owned by the service."""
    with AcquisitionControlManager() as manager:
        assert not hasattr(manager.acquisition, "close")


@posix_only
def test_service_uses_unix_socket(dummy_service, nexus_runtime_dir: Path) -> None:
    """The service listens on a unix domain socket in the runtime directory, not on a TCP port."""
    assert dummy_service.address == str(nexus_runtime_dir / "nexus.sock")
    assert (nexus_runtime_dir / "nexus.sock").is_socket()


@posix_only
@pytest.mark.usefixtures("dummy_service")
def test_runtime_files_permissions(nexus_runtime_dir: Path) -> None:
    """Every account can read the key and the runtime directory, only the service account can write to it."""
    assert stat.S_IMODE((nexus_runtime_dir / "authkey").stat().st_mode) == 0o644
    assert stat.S_IMODE(nexus_runtime_dir.stat().st_mode) == 0o755


@posix_only
def test_key_is_not_replaced_by_a_second_instance(dummy_service, nexus_runtime_dir: Path) -> None:
    """A second service fails to bind the socket of the running one and leaves its key untouched."""
    key = (nexus_runtime_dir / "authkey").read_bytes()
    second = AcquisitionControlManager(callable_acq_control=DummyAcquisitionControl, address=dummy_service.address)

    with pytest.raises(OSError):  # the address is taken by the running service
        second.get_server()

    assert (nexus_runtime_dir / "authkey").read_bytes() == key


@posix_only
def test_service_refuses_runtime_dir_of_another_account(
    nexus_runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The service does not start in a directory whose owner could replace its socket and key."""
    nexus_runtime_dir.mkdir()
    _owned_by_another_account(nexus_runtime_dir, monkeypatch)

    with pytest.raises(RuntimeError, match="belongs to"):
        claim_runtime_dir(nexus_runtime_dir, service_address())


def test_release_removes_empty_runtime_dir(nexus_runtime_dir: Path) -> None:
    """Nothing is left behind after a shutdown, so any account can start the service afterwards."""
    claim_runtime_dir(nexus_runtime_dir, service_address())

    release_runtime_dir(nexus_runtime_dir)

    assert not nexus_runtime_dir.exists()


@pytest.mark.usefixtures("dummy_service")
def test_release_keeps_files_of_running_service(nexus_runtime_dir: Path) -> None:
    """An instance which failed to bind the socket must not remove socket and key of the running service."""
    release_runtime_dir(nexus_runtime_dir)

    with AcquisitionControlManager() as manager:
        assert manager.acquisition.get_progress() == 42


@pytest.mark.usefixtures("nexus_runtime_dir")
def test_tcp_address_is_rejected() -> None:
    """A TCP address of the former API is reported instead of being misread as socket path."""
    with pytest.raises(TypeError, match="TCP"):
        AcquisitionControlManager(address=("localhost", 50000), authkey=b"secretkey")


@pytest.mark.usefixtures("dummy_service")
def test_wrong_authkey_is_explained() -> None:
    """A key which does not match the running service is reported with a hint."""
    with pytest.raises(AuthenticationError, match="rejected the authentication key"), AcquisitionControlManager(
        authkey=b"outdated"
    ):
        pass


@pytest.mark.usefixtures("nexus_runtime_dir")
def test_client_without_authkey() -> None:
    """Constructing a client without a running service reports the service state."""
    with pytest.raises(NexusNotRunningError, match="systemctl start nexus"):
        AcquisitionControlManager()


@pytest.mark.usefixtures("nexus_runtime_dir")
def test_client_without_service() -> None:
    """Entering the context without a listening service reports the service state."""
    manager = AcquisitionControlManager(authkey=b"key")

    with pytest.raises(NexusNotRunningError, match="systemctl start nexus"):
        manager.__enter__()


@posix_only
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


@posix_only
def test_missing_system_runtime_dir_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the systemd directory the temporary directory is used as before."""
    fallback = tmp_path / "tmp"
    monkeypatch.delenv("NEXUS_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(acquisition_manager, "SYSTEM_RUNTIME_DIR", tmp_path / "run" / "nexus")
    monkeypatch.setattr(acquisition_manager.tempfile, "gettempdir", lambda: str(fallback))

    assert runtime_dir() == fallback / "nexus"


def test_stale_socket_is_removed(nexus_runtime_dir: Path) -> None:
    """The leftover directory of a killed service of the same account is reused, its socket and key removed."""
    nexus_runtime_dir.mkdir()
    (nexus_runtime_dir / "authkey").write_bytes(b"stale")
    address = service_address()
    # A killed service cannot clean up: its socket file survives, a named pipe on Windows vanishes with it
    killed = f"import os, multiprocessing.connection as c; listener = c.Listener({address!r}); os._exit(0)"
    subprocess.run([sys.executable, "-c", killed], check=True)  # noqa: S603
    assert Path(address).exists() or sys.platform == "win32"

    claim_runtime_dir(nexus_runtime_dir, address)

    assert not Path(address).exists()
    assert not (nexus_runtime_dir / "authkey").exists()


def test_live_socket_aborts_startup(nexus_runtime_dir: Path) -> None:
    """A socket with a live service behind it must not be removed."""
    nexus_runtime_dir.mkdir()
    address = service_address()

    with Listener(address):
        with pytest.raises(RuntimeError, match="already running"):
            claim_runtime_dir(nexus_runtime_dir, address)
        with pytest.raises(OSError):  # the address is still taken by the live service
            Listener(address)


@posix_only
def test_runtime_dir_is_created(nexus_runtime_dir: Path) -> None:
    """Without a leftover, the directory is created for the service account, regardless of the umask."""
    umask = os.umask(0o077)
    try:
        claim_runtime_dir(nexus_runtime_dir, service_address())
    finally:
        os.umask(umask)

    assert stat.S_IMODE(nexus_runtime_dir.stat().st_mode) == 0o755
    assert not Path(service_address()).exists()
