"""Start acquisition control manager service/process."""
import argparse
import atexit
import logging
import os
import signal
import sys
from contextlib import suppress
from multiprocessing.connection import Client
from multiprocessing.managers import Server
from pathlib import Path

from console.spcm_control.acquisition_control import AcquisitionControl
from nexus_service.acquisition_manager import AcquisitionControlManager, runtime_dir, service_address


def claim_runtime_dir(directory: Path, address: str) -> None:
    """Prepare the runtime directory for this service, before any hardware is touched.

    The directory is created for the service account with mode 755: every account can read the key and connect
    to the socket, but no other account can place files in it. A leftover of a killed service of the same
    account is reused, its socket file and key are removed.

    Parameters
    ----------
    directory
        Runtime directory of the service.
    address
        Path of the unix domain socket (name of the named pipe on Windows) of the acquisition service.

    Raises
    ------
    RuntimeError
        If a service is already running, or if the directory belongs to another account, e.g. as leftover of
        a killed service. In the sticky temporary directory, only that account or root can remove it.
    """
    try:
        Client(address).close()
    except (ConnectionRefusedError, FileNotFoundError, PermissionError):
        pass  # nobody reachable is listening
    else:
        raise RuntimeError(f"A nexus service is already running on {address}.")
    try:
        directory.mkdir(parents=True)
    except FileExistsError:
        # A symbolic link is judged by its own owner, so it cannot redirect the service into a foreign directory
        if sys.platform != "win32" and directory.lstat().st_uid != os.getuid():
            owner = directory.owner(follow_symlinks=False)
            raise RuntimeError(
                f"{directory} belongs to {owner}, e.g. as leftover of a killed service. "
                f"Ask {owner} or an administrator to remove it."
            ) from None
    directory.chmod(0o755)  # mkdir applies the umask
    # A named pipe vanishes with its server, but socket file and key of a killed service are left behind
    Path(address).unlink(missing_ok=True)
    (directory / "authkey").unlink(missing_ok=True)


def release_runtime_dir(directory: Path) -> None:
    """Remove the runtime directory if it is empty, so that any account can start the service again.

    Socket and key are removed before by the service which published them. If the directory still holds those
    of a running service, e.g. after this instance failed to bind the socket, it is kept. Under systemd, the
    service account may not remove ``/run/nexus``, systemd removes it on stop instead.
    """
    with suppress(OSError):
        directory.rmdir()


def main() -> None:
    """Start the acquisition service (command line entry point ``nexus``).

    Connects the measurement cards via `AcquisitionControl` and serves this instance through an
    `AcquisitionControlManager` (``multiprocessing.managers.BaseManager``) on the unix domain socket in the
    runtime directory, so that acquisitions can be run from other processes on the workstation.

    Command line arguments:

    - ``-d``, ``--device_config``: path to the device configuration YAML file (required).
    - ``-l``, ``--log_dir``: directory of the log file ``<date>_nexus.log`` (default ``<home>/nexus-console``).
    - ``-n``, ``--no-verify``: skip the confirmation prompt that all amplifiers are switched off.
      The XIO outputs of the cards are pulled high while the cards are opened.
    """
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

    # Claim the runtime directory before any hardware is touched, and release it on every exit from here on
    directory = runtime_dir()
    address = service_address()
    claim_runtime_dir(directory, address)

    acquisition_control: AcquisitionControl | None = None
    server: Server | None = None

    def shutdown_handler() -> None:
        try:
            print("\n[nexus] Shutting down nexus server...\n")
            if acquisition_control is not None:
                acquisition_control.close()
                print("[nexus] Acquisition control shutdown successfully.")
        except Exception as e:  # noqa: BLE001 - atexit handler must not raise, report any error instead
            print(f"[nexus] Error during shutdown: {e}")
        finally:
            # Only a service which bound the socket removes socket and key, an instance which failed to bind
            # must leave those of the running service alone
            if server is not None:
                server.listener.close()  # type: ignore[attr-defined]  # removes the socket, missing in typeshed
                manager.key_file.unlink(missing_ok=True)
            release_runtime_dir(directory)
            print("[nexus] Shutdown complete.")

    atexit.register(shutdown_handler)
    # Run the atexit handlers on SIGTERM (systemctl stop) and SIGHUP (terminal closed) as well, otherwise socket,
    # key and directory would be left behind. A service started with nohup ignores SIGHUP and keeps running.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    if sys.platform != "win32" and signal.getsignal(signal.SIGHUP) is not signal.SIG_IGN:
        signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))

    if not args.no_verify:
        input("\n[nexus] Before starting the setup, confirm that all the amplifiers are turned off.\
            \nPress Enter to continue...")
    print("\n[nexus] Setting up the acquisition control...\n")

    # Setup global acquisition control with argparse arguments
    acquisition_control = AcquisitionControl(
        configuration=args.device_config,
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

    print(f"\n[nexus] AcquisitionControlManager >> Server started on {address}...\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
