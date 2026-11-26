"""System information for hardware test reports: OS, repository revision, Spectrum driver and cards.

Can be run on its own to display the current state of the system, from the repository root:

    python tests/hardware/system_info.py

The Spectrum cards are found through the spcm driver, which names them /dev/spcm0, /dev/spcm1, ... on all operating
systems. Each card is opened briefly to read model, function and number of channels, and closed again without being
reset or configured. A card that is in use by another process, e.g. a running console service, cannot be opened; it is
listed together with the driver error.
"""
import ctypes
import platform
import subprocess
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MAX_CARDS = 16  # Number of probed card device names /dev/spcm<k>
TX = "TX"  # Function of the transmit card (analog output, arbitrary waveform generator)
RX = "RX"  # Function of the receive card (analog input, digitizer)


@dataclass
class CardInfo:
    """Information about one Spectrum card."""

    path: str
    model: str | None = None
    function: str | None = None  # E.g. TX or RX
    num_channels: int | None = None
    error: str | None = None  # Reason why the card could not be opened

    def __str__(self) -> str:
        """Return human readable summary."""
        return f"{self.model} ({self.function}, {self.num_channels} channels)" if self.model else str(self.error)


@dataclass
class SystemInfo:
    """Information about the system the console runs on."""

    os: str
    python: str
    package_version: str
    git_revision: str
    driver: str  # Version of the driver library and kernel driver, or why the driver is not available
    cards: list[CardInfo] = field(default_factory=list)

    def __str__(self) -> str:
        """Return human readable summary."""
        return "\n".join([
            f"OS: {self.os}",
            f"Python: {self.python}",
            f"nexus-console: {self.package_version} | {self.git_revision}",
            f"SPCM driver: {self.driver}",
            f"Spectrum cards: {len(self.cards) or 'none found'}",
            *(f"  {card.path}: {card}" for card in self.cards),
        ])


def os_name() -> str:
    """Return name and version of the operating system, including the distribution on Linux."""
    try:
        return f"{platform.freedesktop_os_release()['PRETTY_NAME']} ({platform.platform()})"
    except (OSError, KeyError):  # No os-release file, e.g. on Windows
        return platform.platform()


def git_revision() -> str:
    """Return branch and commit hash of the repository, flagged if tracked files contain uncommitted changes."""
    def git(*args: str) -> str:
        cmd = ["git", "-C", str(Path(__file__).parent), *args]
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603

    try:
        dirty = " (uncommitted changes)" if git("status", "--porcelain", "--untracked-files=no") else ""
        return f"{git('rev-parse', '--abbrev-ref', 'HEAD')} @ {git('rev-parse', 'HEAD')}{dirty}"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def package_version() -> str:
    """Return the installed version of the nexus-console package."""
    try:
        return version("nexus-console")
    except PackageNotFoundError:
        return "not installed"


def driver_version(value: int) -> str:
    """Decode a version register value of the spcm driver."""
    return f"{value >> 24}.{(value >> 16) & 0xFF} build {value & 0xFFFF}"


def query_driver() -> tuple[str, list[CardInfo]]:
    """Return the driver version and the Spectrum cards found by the driver."""
    try:
        import spcm_core as sp
    except Exception as exc:  # noqa: BLE001, spcm_core raises a bare Exception if the driver is missing or outdated
        return f"not available ({exc})", []

    from console.spcm_control.abstract_device import type_to_name

    def read(handle: object, register: int) -> int:
        """Read a register of a card, or of the driver if the handle is None."""
        value = sp.int64(0)
        sp.spcm_dwGetParam_i64(handle, register, ctypes.byref(value))
        return value.value

    functions = {sp.SPCM_TYPE_AI: RX, sp.SPCM_TYPE_AO: TX, sp.SPCM_TYPE_DI: "digital input",
                 sp.SPCM_TYPE_DO: "digital output", sp.SPCM_TYPE_DIO: "digital input/output"}
    driver = f"library {driver_version(read(None, sp.SPC_GETDRVVERSION))}"
    kernel_version = None
    cards = []
    for path in (f"/dev/spcm{k}" for k in range(MAX_CARDS)):
        handle = sp.spcm_hOpen(ctypes.create_string_buffer(path.encode()))
        if not handle:
            # The error of a failed open is read with a NULL handle, device names without a card are skipped
            msg = ctypes.create_string_buffer(sp.ERRORTEXTLEN)
            if sp.spcm_dwGetErrorInfo_i32(None, None, None, msg) != sp.errors.ERR_BOARDNOTFOUND:
                cards.append(CardInfo(path, error=f"cannot open, {msg.value.decode(errors='replace').strip()}"))
            continue
        try:
            cards.append(CardInfo(
                path,
                model=type_to_name(read(handle, sp.SPC_PCITYP)),
                function=functions.get(read(handle, sp.SPC_FNCTYPE), "unknown function"),
                num_channels=read(handle, sp.SPC_MIINST_MODULES) * read(handle, sp.SPC_MIINST_CHPERMODULE),
            ))
            kernel_version = driver_version(read(handle, sp.SPC_GETKERNELVERSION))
        finally:
            sp.spcm_vClose(handle)
    return f"{driver}, kernel {kernel_version or 'unknown'}", cards


def system_info() -> SystemInfo:
    """Collect information about the operating system, repository, spcm driver and Spectrum cards.

    The cards are opened briefly. Must be called while no other process uses the cards, e.g. before the acquisition
    control is created.
    """
    driver, cards = query_driver()
    return SystemInfo(
        os=os_name(),
        python=platform.python_version(),
        package_version=package_version(),
        git_revision=git_revision(),
        driver=driver,
        cards=cards,
    )


if __name__ == "__main__":
    print(system_info())
