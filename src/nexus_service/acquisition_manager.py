"""Implementation of nexus acquisition manager for multiprocessing."""
import inspect
import os
import secrets
import sys
import tempfile
from collections.abc import Callable
from multiprocessing import AuthenticationError
from multiprocessing.managers import BaseManager, Server
from pathlib import Path
from types import TracebackType
from typing import Any

from console.spcm_control.acquisition_control import AcquisitionControl

# Alias required within the manager class body, where `AcquisitionControl` is shadowed by the proxy factory
_AcquisitionControl = AcquisitionControl

# Define the AcquisitionControl methods served to clients, shutdown is owned by the service and not exposed
METHODS = tuple(
    name for name, _ in inspect.getmembers(_AcquisitionControl, inspect.isfunction)
    if not name.startswith("_") and name != "close"
)

NOT_RUNNING_MSG = "Nexus service is not running. Start it with: systemctl start nexus, or by hand: nexus -d <config>"
# Created and removed by systemd (RuntimeDirectory= in deployment/nexus.service), owned by the service account
SYSTEM_RUNTIME_DIR = Path("/run/nexus")


class NexusNotRunningError(ConnectionError):
    """The acquisition service is not reachable."""


def runtime_dir() -> Path:
    """Return the directory holding socket and authentication key of the service.

    ``NEXUS_RUNTIME_DIR`` overrides the location (used by the tests). Otherwise, if the service runs as
    a systemd unit, ``/run/nexus`` exists and is used: systemd creates it for the service account and
    removes it on stop. Without the unit the location defaults to ``<tempdir>/nexus``, which the service
    started by hand creates for its account and removes on shutdown. Every account may use the console,
    so the directory and the key are readable and the socket is accessible by every account, but only the
    service account can place files in the directory. This function neither creates nor checks the
    directory, the service does (see ``nexus_service.start_manager.claim_runtime_dir``).

    Returns
    -------
        Path of the runtime directory.
    """
    if "NEXUS_RUNTIME_DIR" not in os.environ and SYSTEM_RUNTIME_DIR.is_dir() and not SYSTEM_RUNTIME_DIR.is_symlink():
        return SYSTEM_RUNTIME_DIR
    return Path(os.environ.get("NEXUS_RUNTIME_DIR", Path(tempfile.gettempdir()) / "nexus"))


def service_address() -> str:
    """Return the address of the service, the unix domain socket in the runtime directory.

    Windows has no unix domain sockets, a named pipe named after the socket path serves instead.
    """
    address = runtime_dir() / "nexus.sock"
    if sys.platform == "win32":
        return rf"\\.\pipe\{address.as_posix()}"
    else:
        return str(address)


class AcquisitionControlManager(BaseManager):
    """Acquisition control manager.

    The manager connects to the acquisition service through a unix domain socket
    in the nexus runtime directory. Address and authentication key are resolved
    from that directory. It can be used as follows:

        with AcquisitionControlManager() as manager:
            manager.acquisition.set_sequence(sequence=seq, parameter=parameter)
            acquisition_data = manager.acquisition.run()

    The service side passes ``callable_acq_control`` and thereby generates a fresh
    authentication key for this run, which is published in the runtime directory
    by ``get_server()`` or ``start()`` once the socket is bound.

    Raises
    ------
    NexusNotRunningError
        If no authentication key is found, i.e. the acquisition service is not running.
    TypeError
        If the address is not a socket path, e.g. a TCP address of the former API.
    """

    # Proxy factory, added dynamically by BaseManager.register("AcquisitionControl") in __init__
    AcquisitionControl: Callable[[], _AcquisitionControl]

    def __init__(
        self,
        address: str | Path | None = None,
        authkey: bytes | None = None,
        callable_acq_control: Callable[[], _AcquisitionControl] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the acquisition control manager.

        Parameters
        ----------
        address : str or Path or None, optional
            Address of the manager process, by default None.
            If None, the unix domain socket in the runtime directory is used.
            TCP addresses, i.e. ``(host, port)`` tuples, are not supported.
        authkey : bytes or None, optional
            Authentication key of the manager process, by default None.
            If None, a fresh key is generated on the service side
            and read from the runtime directory on the client side.
        callable_acq_control : Callable[[], AcquisitionControl] or None, optional
            Callable which returns the acquisition control instance served by the manager, by default None.
            If None, the acquisition control is registered without callable (client side).
        **kwargs
            Additional keyword arguments passed to ``BaseManager``.
        """
        if address is not None and not isinstance(address, str | Path):
            raise TypeError(
                f"Address must be the path of the service socket, got {address!r}. The service does not listen on a "
                "TCP port anymore, construct the manager without address and authkey to connect to the local service."
            )
        self.key_file = runtime_dir() / "authkey"
        # Key generated by the service, published by get_server() or start() once the socket is bound
        self._generated_key: bytes | None = None
        if authkey is None and callable_acq_control:
            authkey = self._generated_key = secrets.token_bytes(32)
        elif authkey is None:
            try:
                authkey = self.key_file.read_bytes()
            except FileNotFoundError as exc:
                raise NexusNotRunningError(NOT_RUNNING_MSG) from exc

        super().__init__(address=str(address or service_address()), authkey=authkey, **kwargs)
        # Dynamically register acquisition control and the acquisition parameter proxy
        if callable_acq_control:
            self.register("AcquisitionControl", callable=callable_acq_control, exposed=METHODS)
        else:
            self.register("AcquisitionControl")

    def get_server(self) -> Server:
        """Bind the socket and return the server, then publish the authentication key."""
        server = super().get_server()
        self._publish_authkey()
        return server

    def start(self, *args: Any, **kwargs: Any) -> None:
        """Start the server in a child process, then publish the authentication key."""
        super().start(*args, **kwargs)
        self._publish_authkey()

    def _publish_authkey(self) -> None:
        """Write the generated key to the runtime directory.

        Only called once the socket is bound, so a second service instance, which fails to bind, cannot replace
        the key of the running one.
        """
        if self._generated_key is None:
            return
        self.key_file.write_bytes(self._generated_key)
        self.key_file.chmod(0o644)

    def __enter__(self) -> "AcquisitionControlManager":
        """Enter with context.

        Raises
        ------
        NexusNotRunningError
            If the acquisition service is not reachable at the runtime socket.
        PermissionError
            If the account may not connect to the socket or named pipe.
        AuthenticationError
            If the service rejects the authentication key.
        """
        address = str(self.address)
        try:
            self.connect()
        except (ConnectionRefusedError, FileNotFoundError) as exc:
            raise NexusNotRunningError(NOT_RUNNING_MSG) from exc
        except PermissionError as exc:
            raise PermissionError(
                f"No permission to connect to the nexus service at {address}. "
                "On Windows, only the account which started the service can connect."
            ) from exc
        except AuthenticationError as exc:
            raise AuthenticationError(
                f"The nexus service at {address} rejected the authentication key. Construct the manager without "
                "authkey to use the key of the running service, and construct it anew after a service restart."
            ) from exc
        self.acquisition: AcquisitionControl = self.AcquisitionControl()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit with context."""
        # Explicitly remove the proxy references
        if hasattr(self, "acquisition"):
            del self.acquisition
        # Returning None propagates exceptions if they occur, traceback is printed by the caller
