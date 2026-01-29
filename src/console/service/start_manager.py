"""Start acquisition control manager service/process."""
import argparse
import atexit
import logging
import os
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
    parser.add_argument(
        "-n",
        "--no-verify",
        action="store_true",
        help="If this flag is set, the service starts immedietly without asking the user to confirm that hardware is turned off.",
    )
    args = parser.parse_args()
    if not args.no_verify:
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

    server = manager.get_server()

    def shutdown_handler():
        try:
            print("\n[neXus] Shutting down nexus server...\n")
            if acquisition_control:
                acquisition_control.__del__()
                print("[neXus] Acquisition control shutdown successfully.")
        except Exception as e:
            print(f"[neXus] Error during shutdown: {e}")
        finally:
            print("[neXus] Shutdown complete.")

    atexit.register(shutdown_handler)

    print(f"\n[neXus] AcquisitionControlManager >> Server started on port {args.port}...\n")
    server.serve_forever()


if __name__ == '__main__':
    main()
