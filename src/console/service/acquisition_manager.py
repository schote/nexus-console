"""Implementation of nexus acquisition manager for multiprocessing."""
import os
import secrets
import stat
import tempfile
import traceback
from collections.abc import Callable
from contextlib import suppress
from multiprocessing.managers import BaseManager
from pathlib import Path

from console.spcm_control.acquisition_control import AcquisitionControl

NOT_RUNNING_MSG = "Nexus service is not running. Start it with: systemctl start nexus"


class NexusNotRunningError(ConnectionError):
    """The acquisition service is not reachable."""


def runtime_dir() -> Path:
    """Return the directory holding socket and authentication key of the service.

    Defaults to ``<tempdir>/nexus``, ``NEXUS_RUNTIME_DIR`` overrides the location (used by the tests).
    The directory is created on demand with mode 1777: every account may use the console, so every
    account must be able to read the key and open the socket, while the sticky bit keeps one account
    from removing the files of another. A symbolic link or a directory with different permissions,
    which could have been pre-created by another user, is refused.

    Returns
    -------
        Path of the runtime directory.

    Raises
    ------
    RuntimeError
        If the runtime directory is a symbolic link or has unexpected permissions.
    """
    path = Path(os.environ.get("NEXUS_RUNTIME_DIR", Path(tempfile.gettempdir()) / "nexus"))
    if path.is_symlink():
        raise RuntimeError(f"Runtime directory {path} is a symbolic link, refusing to use it.")
    path.mkdir(parents=True, exist_ok=True)
    with suppress(PermissionError):  # directory may belong to the account which started the service
        path.chmod(0o1777)
    if stat.S_IMODE(path.stat().st_mode) != 0o1777:
        raise RuntimeError(f"Runtime directory {path} has wrong permissions, remove it or set NEXUS_RUNTIME_DIR.")
    return path


class AcquisitionControlManager(BaseManager):
    """Acquisition control manager.

    The manager connects to the acquisition service through a unix domain socket
    in the nexus runtime directory. Address and authentication key are resolved
    from that directory. It can be used as follows:

        with AcquisitionControlManager() as manager:
            manager.acquisition.set_sequence(sequence=seq, parameter=parameter)
            acquisition_data = manager.acquisition.run()

    The service side passes ``callable_acq_control`` and thereby generates a fresh
    authentication key for this run, which is published in the runtime directory.

    Raises
    ------
    NexusNotRunningError
        If no authentication key is found, i.e. the acquisition service is not running.
    """

    def __init__(
        self,
        address: str | Path | None = None,
        authkey: bytes | None = None,
        callable_acq_control: Callable | None = None,
        **kwargs,
    ):
        key_file = runtime_dir() / "authkey"
        if authkey is None and callable_acq_control:
            authkey = secrets.token_bytes(32)
            key_file.write_bytes(authkey)
            key_file.chmod(0o644)
        elif authkey is None:
            try:
                authkey = key_file.read_bytes()
            except FileNotFoundError as exc:
                raise NexusNotRunningError(NOT_RUNNING_MSG) from exc

        super().__init__(address=str(address or runtime_dir() / "nexus.sock"), authkey=authkey, **kwargs)
        # Dynamically register acquisition control and the acquisition parameter proxy
        if callable_acq_control:
            self.register('AcquisitionControl', callable=callable_acq_control)
        else:
            self.register('AcquisitionControl')

    def __enter__(self) -> "AcquisitionControlManager":
        """Enter with context.

        Raises
        ------
        NexusNotRunningError
            If the acquisition service is not reachable at the runtime socket.
        """
        try:
            self.connect()
        except (ConnectionRefusedError, FileNotFoundError) as exc:
            raise NexusNotRunningError(NOT_RUNNING_MSG) from exc
        self.acquisition: AcquisitionControl = getattr(self, "AcquisitionControl")()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Exit with context."""
        # Explicitly remove the proxy references
        if hasattr(self, "acquisition"):
            del self.acquisition

        if exc_type is not None:
            print(f"An error occurred: {exc_value}")
            traceback.print_tb(exc_tb)

        return False  # Propagate exceptions if they occur
