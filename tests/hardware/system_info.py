"""System information for hardware test reports: OS, repository revision, Spectrum cards and driver.

Can be run on its own to display the current state of the system, from the repository root:

    python tests/hardware/system_info.py

Card model and driver library version are read from the card through the spcm driver. Each card is
opened briefly and closed again without being reset or configured. A card that is in use by another process, e.g. a
running console service, cannot be opened; it is listed together with the driver error.
"""
import ctypes
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MAX_PROBED_CARDS = 16  # Upper bound for card indices probed if device nodes cannot be listed (Windows)


@dataclass
class CardInfo:
    """Information about one Spectrum card."""

    path: str
    model: str | None = None
    error: str | None = None  # Reason why the card could not be opened


@dataclass
class SystemInfo:
    """Information about the system the console runs on."""

    os: str
    python: str
    package_version: str
    git_revision: str
    driver_loaded: bool
    driver_error: str | None = None
    library_version: str | None = None  # Driver library (libspcm_linux.so, spcm_win64.dll)
    kernel_driver_version: str | None = None
    cards: list[CardInfo] = field(default_factory=list)

    def __str__(self) -> str:
        """Return human readable summary."""
        driver = f"library {self.library_version or 'unknown'}, kernel {self.kernel_driver_version or 'unknown'}"
        if not self.driver_loaded:
            driver = f"not loaded ({self.driver_error})"
        lines = [
            f"OS: {self.os}",
            f"Python: {self.python}",
            f"nexus-console: {self.package_version} | {self.git_revision}",
            f"SPCM driver: {driver}",
            f"Spectrum cards: {len(self.cards) or 'none found'}",
        ]
        for card in self.cards:
            lines.append(f"  {card.path}: {card.model or card.error}")
        return "\n".join(lines)


def os_name() -> str:
    """Return name and version of the operating system."""
    match platform.system():
        case "Linux":
            try:
                distribution = platform.freedesktop_os_release().get("PRETTY_NAME", "Linux")
            except OSError:
                distribution = "Linux"
            return f"{distribution} (kernel {platform.release()})"
        case "Windows":
            return f"Windows {platform.release()} (version {platform.version()}, edition {platform.win32_edition()})"
        case "Darwin":
            return f"macOS {platform.mac_ver()[0]}"
        case _:
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


def linux_kernel_driver_version() -> str | None:
    """Return version of the loaded spcm kernel module, available without opening a card (Linux only)."""
    for module in sorted(Path("/sys/module").glob("spcm*")):
        try:
            return (module / "version").read_text().strip()
        except OSError:
            continue
    return None


def device_paths() -> list[str] | None:
    """Return device paths of the Spectrum cards, None if they cannot be listed without the driver (Windows)."""
    if os.name != "posix":
        return None
    nodes = [p for p in Path("/dev").glob("spcm*") if re.fullmatch(r"spcm\d+", p.name)]
    return [str(p) for p in sorted(nodes, key=lambda p: int(p.name[4:]))]


def query_cards(info: SystemInfo, paths: list[str] | None) -> None:
    """Open each card briefly to read model and driver versions.

    If `paths` is None, card indices are probed until a card cannot be opened.
    """
    import console.spcm_control.spcm.pyspcm as sp
    from console.spcm_control.spcm.tools import type_to_name

    probe = paths is None
    for path in (f"/dev/spcm{k}" for k in range(MAX_PROBED_CARDS)) if probe else paths:
        card = sp.spcm_hOpen(ctypes.create_string_buffer(path.encode()))
        if not card:
            if probe:
                break
            # Error of a failed open is read with a NULL handle
            msg = ctypes.create_string_buffer(sp.ERRORTEXTLEN)
            sp.spcm_dwGetErrorInfo_i32(None, None, None, msg)
            info.cards.append(CardInfo(path, error=f"cannot open, {msg.value.decode(errors='replace').strip()}"))
            continue
        try:
            values = {}
            for register in (sp.SPC_PCITYP, sp.SPC_GETDRVVERSION, sp.SPC_GETKERNELVERSION):
                value = sp.int32(0)
                sp.spcm_dwGetParam_i32(card, register, ctypes.byref(value))
                values[register] = value.value
        finally:
            sp.spcm_vClose(card)
        info.cards.append(CardInfo(path, type_to_name(values[sp.SPC_PCITYP])))
        info.library_version = driver_version(values[sp.SPC_GETDRVVERSION])
        info.kernel_driver_version = driver_version(values[sp.SPC_GETKERNELVERSION])


def system_info(query: bool = True) -> SystemInfo:
    """Collect information about the operating system, repository, spcm driver and Spectrum cards.

    Parameters
    ----------
    query
        If set, cards are opened briefly to read model and driver versions. Otherwise, cards are only
        listed by their device nodes (Linux).
        Must be called while no other process uses the cards, e.g. before the acquisition control is created.
    """
    info = SystemInfo(
        os=os_name(),
        python=platform.python_version(),
        package_version=package_version(),
        git_revision=git_revision(),
        driver_loaded=False,
        kernel_driver_version=linux_kernel_driver_version(),
    )
    paths = device_paths()
    try:
        import console.spcm_control.spcm.pyspcm as sp
        info.driver_loaded = sp.spcmDll is not None
        info.driver_error = getattr(sp, "_driver_error", None) or (None if info.driver_loaded else "not available")
    except Exception as exc:  # noqa: BLE001
        info.driver_error = str(exc)

    if query and info.driver_loaded:
        query_cards(info, paths)
    elif paths:
        info.cards = [CardInfo(p, error="not queried" if info.driver_loaded else "driver not loaded") for p in paths]
    return info


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Display information about the system and the Spectrum cards.")
    parser.add_argument(
        "-n", "--no-query", action="store_true", help="Do not open the cards, only list device nodes (Linux).",
    )
    print(system_info(query=not parser.parse_args().no_query))
