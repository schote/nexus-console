"""Start acquisition control manager service/process."""
import argparse
import atexit
import logging
import os
import signal
import sys
from pathlib import Path

from console.service.acquisition_manager import AcquisitionControlManager
from console.spcm_control.acquisition_control import AcquisitionControl

# acquisition_control: AcquisitionControl | None = None


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
        "-k",
        "--authkey",
        type=str,
        default=b"secretkey",
        help="Manager process authentication key, must be a bytestring",
    )
    parser.add_argument(
        "-a",
        "--address",
        type=str,
        default="localhost",
        help="Manager process connection address",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=50000,
        help="Manager process connection port",
    )
    args = parser.parse_args()
    input("\n[neXus] Before starting the setup, confirm that all the amplifiers are turned off.\
        \nPress Enter to continue...")
    print("\n[neXus] Setting up the acquisition control...\n")

    # Setup global acquisition control with argparse arguments
    # global acquisition_control
    acquisition_control = AcquisitionControl(
        configuration_file=args.device_config,
        nexus_data_dir=args.sessions_folder,
        console_log_level=logging.INFO,
        file_log_level=logging.INFO
    )

    manager = AcquisitionControlManager(
        callable_acq_control=lambda: acquisition_control,
        address=(args.address, args.port),
        authkey=args.authkey,
    )

    # server = manager.get_server()
    manager.start()

    def shutdown_handler(signum=None, frame=None):
        if signum:
            print(f"\n[neXus] Stopping nexus server, received signal: {signum}...")
        else:
            print("\n[neXus] Stopping nexus server...")
        try:
            manager.shutdown()  # Properly shutdown the manager
            print("[neXus] Manager/service shutdown successfully.")
        except Exception as e:
            print(f"[neXus] Failed to shutdown server: {e}")
        finally:
            acquisition_control.__del__()
            sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)   # Ctrl+C
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown_handler)  # Unix, WSL, some service tools
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, shutdown_handler)  # Windows: Ctrl+Break

    atexit.register(shutdown_handler)

    print(f"\n[neXus] AcquisitionControlManager >> Server started on port {args.port}...\n")
    # server.serve_forever()


if __name__ == '__main__':
    main()
