"""Implementation of nexus acquisition manager for multiprocessing."""
import traceback
from collections.abc import Callable
from multiprocessing.managers import BaseManager
from pathlib import Path

from console import NexusNotRunningError
from console.service.authkey import read_authkey
from console.service.paths import socket_path
from console.spcm_control.acquisition_control import AcquisitionControl


class AcquisitionControlManager(BaseManager):
    """Acquisition control manager.

    The manager connects to the acquisition service through a unix domain socket
    in the nexus runtime directory. Address and authentication key are resolved
    from that directory. It can be used as follows:

        with AcquisitionControlManager() as manager:
            manager.acquisition.set_sequence(sequence=seq, parameter=parameter)
            acquisition_data = manager.acquisition.run()
    """

    def __init__(
        self,
        address: str | Path | None = None,
        authkey: bytes | None = None,
        callable_acq_control: Callable | None = None,
        **kwargs,
    ):
        super().__init__(
            address=str(address or socket_path()),
            authkey=authkey or read_authkey(),
            **kwargs,
        )
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
            msg = "Nexus service is not running. Start it with: systemctl start nexus"
            raise NexusNotRunningError(msg) from exc
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
