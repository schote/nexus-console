"""Start acquisition control manager service/process."""
import argparse
import atexit
import logging
import os
import signal
import socket
from pathlib import Path

from console import NexusServiceError
from console.service.acquisition_manager import AcquisitionControlManager
from console.service.authkey import generate_authkey
from console.service.paths import authkey_path, socket_path, verify_runtime_dir
from console.spcm_control.acquisition_control import AcquisitionControl

CONNECT_PROBE_TIMEOUT = 0.5
"""Timeout in seconds when probing an existing socket for a live service."""


def ensure_socket_free(path: Path) -> None:
    """Make sure the service socket can be bound.

    A socket file left behind by a crashed service makes ``bind()`` fail with
    ``EADDRINUSE``. Such a stale socket is removed, a socket with a live service
    behind it aborts the start-up.

    Parameters
    ----------
    path
        Path of the unix domain socket of the acquisition service.

    Raises
    ------
    NexusServiceError
        If another acquisition service is already listening on the socket.
    """
    if not path.exists():
        return

    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(CONNECT_PROBE_TIMEOUT)
    try:
        probe.connect(str(path))
    except (ConnectionRefusedError, FileNotFoundError):
        # Nobody is listening, the socket file is a leftover of a previous run
        path.unlink(missing_ok=True)
    except OSError as exc:
        detail = f"Could not probe existing socket {path}: {exc}"
        raise NexusServiceError(detail) from exc
    else:
        detail = f"A nexus service is already running on {path}."
        raise NexusServiceError(detail)
    finally:
        probe.close()


def _exit_on_signal(signum, frame) -> None:
    """Turn a termination signal into a regular interpreter exit.

    Without this handler the process dies on ``SIGTERM`` without running its
    ``atexit`` handlers, leaving the measurement cards connected and the socket
    and authentication key behind.
    """
    raise SystemExit(0)


def main():
    """Start the acquisition control and setup the manager."""
    parser = argparse.ArgumentParser(description="Start Nexus acquisition service.")
    parser.add_argument(
        "-d",
        "--device_config",
        type=str,
        required=True,
        help="Path to device configuration yaml file.",
    )
    parser.add_argument(
        "-f",
        "--sessions_folder",
        type=str,
        default=os.path.join(Path.home(), "nexus-console"),
        help="Directory to store all the acquisition data acquired during the session.",
    )
    parser.add_argument(
        "--authkey-file",
        type=str,
        default=None,
        help="Path to a file containing the manager authentication key. \
                If omitted, a random key is generated for this service run.",
    )
    # Note, XIO lines have a pull-up -> XIO output is temporarily high when opening the cards:
    # https://github.com/schote/nexus-console/issues/54#issuecomment-2823593549
    parser.add_argument(
        "-n",
        "--no-verify",
        action="store_true",
        help="If this flag is set, the service starts immediately without asking the user for confirmation. \
                Be aware that the outputs of the XIO lines have a pull-up resistor to pull the signal high, \
                    when the card isn't actively setting the output (e.g. when opening the card). \
                        This is the case when starting the service because the cards are opened.",
    )
    args = parser.parse_args()

    # Validate the runtime directory and free the socket before any hardware is touched
    verify_runtime_dir()
    address = socket_path()
    ensure_socket_free(address)

    if not args.no_verify:
        input("\n[neXus] Before starting the setup, confirm that all the amplifiers are turned off.\
            \nPress Enter to continue...")
    print("\n[neXus] Setting up the acquisition control...\n")

    # Setup global acquisition control with argparse arguments
    acquisition_control = AcquisitionControl(
        configuration_file=args.device_config,
        nexus_data_dir=args.sessions_folder,
        console_log_level=logging.INFO,
        file_log_level=logging.INFO
    )
    log = logging.getLogger("Service")

    if args.authkey_file:
        authkey = Path(args.authkey_file).read_bytes()
        log.info("Using authentication key from %s", args.authkey_file)
    else:
        authkey = generate_authkey()
        log.info("Generated authentication key: %s", authkey_path())

    manager = AcquisitionControlManager(
        callable_acq_control=lambda: acquisition_control,
        address=address,
        authkey=authkey,
    )

    server = manager.get_server()
    # Every account may use the console, so every account must be able to connect
    address.chmod(0o666)
    log.info("Acquisition service listening on %s", address)

    def shutdown_handler():
        try:
            print("\n[neXus] Shutting down nexus server...\n")
            if acquisition_control:
                acquisition_control.__del__()
                print("[neXus] Acquisition control shutdown successfully.")
        except Exception as e:
            print(f"[neXus] Error during shutdown: {e}")
        finally:
            address.unlink(missing_ok=True)
            if not args.authkey_file:
                authkey_path().unlink(missing_ok=True)
            print("[neXus] Shutdown complete.")

    atexit.register(shutdown_handler)
    signal.signal(signal.SIGTERM, _exit_on_signal)

    print(f"\n[neXus] AcquisitionControlManager >> Server started on {address}...\n")
    server.serve_forever()


if __name__ == '__main__':
    main()
