"""Start acquisition control manager service/process."""
import argparse
import atexit
import logging
import os
import signal
import socket
import sys
from pathlib import Path

from console.service.acquisition_manager import AcquisitionControlManager, runtime_dir
from console.spcm_control.acquisition_control import AcquisitionControl


def ensure_socket_free(path: Path) -> None:
    """Remove a socket file left behind by a crashed service, abort if a service is listening on it.

    Parameters
    ----------
    path
        Path of the unix domain socket of the acquisition service.

    Raises
    ------
    RuntimeError
        If another acquisition service is already listening on the socket.
    """
    if not path.exists():
        return
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        try:
            probe.connect(str(path))
        except ConnectionRefusedError:
            path.unlink()
            return
    raise RuntimeError(f"A nexus service is already running on {path}.")


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
    address = runtime_dir() / "nexus.sock"
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

    manager = AcquisitionControlManager(
        callable_acq_control=lambda: acquisition_control,
        address=address,
    )

    server = manager.get_server()
    # Every account may use the console, so every account must be able to connect
    address.chmod(0o666)

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
            (runtime_dir() / "authkey").unlink(missing_ok=True)
            print("[neXus] Shutdown complete.")

    atexit.register(shutdown_handler)
    # Run the atexit handlers on SIGTERM (systemctl stop) as well, otherwise socket and key would be left behind
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print(f"\n[neXus] AcquisitionControlManager >> Server started on {address}...\n")
    server.serve_forever()


if __name__ == '__main__':
    main()
