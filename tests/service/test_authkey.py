"""Tests for the generated service authentication key."""
import stat
from pathlib import Path

import pytest

from console import NexusNotRunningError
from console.service.authkey import AUTHKEY_NUM_BYTES, generate_authkey, read_authkey
from console.service.paths import RUNTIME_DIR_MODE, authkey_path
from console.service.paths import runtime_dir as nexus_runtime_dir


def test_generate_authkey_creates_random_key(runtime_dir: Path) -> None:
    """A generated key has the expected size and is different on every call."""
    first = generate_authkey()
    second = generate_authkey()

    assert isinstance(first, bytes)
    assert len(first) == AUTHKEY_NUM_BYTES
    assert first != second


def test_generate_authkey_file_permissions(runtime_dir: Path) -> None:
    """Every account can read the key, only its owner can write it."""
    generate_authkey()

    mode = stat.S_IMODE(authkey_path().stat().st_mode)

    assert mode == 0o644


def test_read_authkey_returns_generated_key(runtime_dir: Path) -> None:
    """The key read back is the key which was written."""
    key = generate_authkey()

    assert read_authkey() == key


def test_read_authkey_without_service(runtime_dir: Path) -> None:
    """A missing key file means the service is not running."""
    with pytest.raises(NexusNotRunningError, match="systemctl start nexus"):
        read_authkey()


def test_runtime_dir_permissions(runtime_dir: Path) -> None:
    """The runtime directory is usable by every account, but files stay their owner's."""
    mode = stat.S_IMODE(authkey_path().parent.stat().st_mode)

    assert mode == RUNTIME_DIR_MODE
    assert mode & stat.S_ISVTX
    assert mode & (stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH) == (
        stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH
    )


def test_runtime_dir_of_a_foreign_owner(runtime_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A client which does not own the directory still resolves it."""
    runtime_dir.mkdir(parents=True, exist_ok=True)

    def _deny(*args: object, **kwargs: object) -> None:
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(Path, "chmod", _deny)

    assert nexus_runtime_dir() == runtime_dir
