"""Start acquisition control manager service/process."""
import argparse
import atexit
import logging
import os
import signal
import sys
from contextlib import suppress
from multiprocessing.connection import Client
from pathlib import Path

from console.spcm_control.acquisition_control import AcquisitionControl
from nexus_service.acquisition_manager import AcquisitionControlManager, runtime_dir, service_address


def ensure_socket_free(address: str | Path) -> None:
    """Remove a socket file left behind by a crashed service, abort if a service is listening on it.

    Parameters
    ----------
    address
        Path of the unix domain socket (name of the named pipe on Windows) of the acquisition service.

    Raises
    ------
    RuntimeError
        If another acquisition service is already listening on the socket.
    """
    try:
        Client(str(address)).close()
    except (ConnectionRefusedError, FileNotFoundError):
        # Nobody is listening, a named pipe vanishes with its server but a socket file is left behind
        with suppress(FileNotFoundError):
            os.unlink(address)
        return
    raise RuntimeError(f"A nexus service is already running on {address}.")


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
        "-l",
        "--log_dir",
        type=Path,
        default=None,
        help="Directory of the log file. Defaults to ~/nexus-console.",
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
    address = service_address()
    ensure_socket_free(address)

    if not args.no_verify:
        input("\n[nexus] Before starting the setup, confirm that all the amplifiers are turned off.\
            \nPress Enter to continue...")
    print("\n[nexus] Setting up the acquisition control...\n")

    # Setup global acquisition control with argparse arguments
    acquisition_control = AcquisitionControl(
        configuration_file=args.device_config,
        log_dir=args.log_dir,
        console_log_level=logging.INFO,
        file_log_level=logging.INFO
    )

    manager = AcquisitionControlManager(
        callable_acq_control=lambda: acquisition_control,
        address=address,
    )

    # Every account may use the console, so every account must be able to connect: create the socket
    # with mode 666 (named pipes on Windows ignore the umask)
    umask = os.umask(0o111)
    try:
        server = manager.get_server()
    finally:
        os.umask(umask)

    def shutdown_handler():
        try:
            print("\n[nexus] Shutting down nexus server...\n")
            if acquisition_control:
                acquisition_control.__del__()
                print("[nexus] Acquisition control shutdown successfully.")
        except Exception as e:
            print(f"[nexus] Error during shutdown: {e}")
        finally:
            # The socket file itself is removed by the finalizer of the multiprocessing listener
            (runtime_dir() / "authkey").unlink(missing_ok=True)
            print("[nexus] Shutdown complete.")

    atexit.register(shutdown_handler)
    # Run the atexit handlers on SIGTERM (systemctl stop) as well, otherwise socket and key would be left behind
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print(f"\n[nexus] AcquisitionControlManager >> Server started on {address}...\n")
    server.serve_forever()


if __name__ == '__main__':
    main()
