"""Resolve nexus runtime paths."""
import os
import stat
import tempfile
from contextlib import suppress
from pathlib import Path

from console import NexusServiceError

RUNTIME_DIR_NAME = "nexus"

RUNTIME_DIR_MODE = 0o1777
"""Permissions of the runtime directory: usable by everyone, with the sticky bit set.

Every account may use the console, so every account must be able to read the key and open
the socket and the lock. It restricts deleting and renaming a file to the account which owns it,
so no session can remove the socket, the key or the lock of another.
"""


def _resolve_runtime_dir() -> Path:
    """Return the location of the nexus runtime directory without creating it."""
    if env := os.environ.get("NEXUS_RUNTIME_DIR"):
        return Path(env)
    return Path(tempfile.gettempdir()) / RUNTIME_DIR_NAME


def runtime_dir() -> Path:
    """Return the nexus runtime directory, creating it if necessary.

    Uses ``<tempdir>/nexus``. ``NEXUS_RUNTIME_DIR`` overrides the location and
    exists so that tests can isolate themselves from a running service.

    The directory is deliberately not scoped per UID: the service and its clients
    may run under different accounts and must resolve to the same location.

    Returns
    -------
        Path of the runtime directory.
    """
    path = _resolve_runtime_dir()
    path.mkdir(parents=True, exist_ok=True)
    with suppress(PermissionError):
        path.chmod(RUNTIME_DIR_MODE)
    return path


def socket_path() -> Path:
    """Path of the acquisition manager unix domain socket."""
    return runtime_dir() / "nexus.sock"


def authkey_path() -> Path:
    """Path of the generated manager authentication key."""
    return runtime_dir() / "authkey"


def lock_path() -> Path:
    """Path of the exclusive hardware lock file."""
    return runtime_dir() / "hardware.lock"


def lock_owner_path() -> Path:
    """Path of the sidecar file describing the current lock holder."""
    return runtime_dir() / "hardware.lock.owner.json"


def verify_runtime_dir() -> Path:
    """Check the runtime directory for squatting and return it.

    The runtime directory has a fixed, predictable name below a world-writable
    location and could therefore be pre-created by another user. This is a
    start-up check for the service only, it is not repeated on every path lookup.

    The owner of the directory is not checked: it is legitimately the account which
    started the service first, which is not necessarily the account running now. What
    matters is that its permissions keep another account from removing our files.

    Returns
    -------
        Path of the verified runtime directory.

    Raises
    ------
    NexusServiceError
        If the runtime directory is a symbolic link, or if its permissions differ from
        :data:`RUNTIME_DIR_MODE`. Where the directory belongs to the current account,
        :func:`runtime_dir` has already corrected the permissions.
    """
    path = _resolve_runtime_dir()
    if path.is_symlink():
        detail = f"Runtime directory {path} is a symbolic link, refusing to use it."
        raise NexusServiceError(detail)

    path = runtime_dir()
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != RUNTIME_DIR_MODE:
        detail = (
            f"Runtime directory {path} has mode {mode:04o}, expected {RUNTIME_DIR_MODE:04o}. "
            "Remove it, or point NEXUS_RUNTIME_DIR at a different location."
        )
        raise NexusServiceError(detail)
    return path


def write_atomic(path: Path, data: bytes, mode: int) -> None:
    """Write a runtime file atomically, so that readers never observe a partial write.

    The payload is written to a temporary file in the same directory, given the
    requested permissions and then moved into place with :func:`os.replace`.

    Parameters
    ----------
    path
        Target path of the file, must reside in the runtime directory.
    data
        Content to write.
    mode
        Permission bits of the resulting file.
    """
    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}-")
    try:
        with os.fdopen(tmp_fd, "wb") as tmp_file:
            tmp_file.write(data)
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
