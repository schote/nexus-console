"""Register and error constants of the spcm_core package, importable without the spectrum driver.

Importing any ``spcm_core`` submodule executes the package ``__init__``, which loads the driver library
and raises if it is not installed. The register and error definitions (``regs.py``, ``spcerr.py``) are
plain constant files without imports, so they are loaded directly from the package directory instead.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:

    def __getattr__(name: str) -> Any:
        """Constants are exported dynamically from the spcm_core files below."""
        raise AttributeError(name)


def _load_module(name: str) -> ModuleType:
    """Load a module file from the spcm_core package without executing the package init.

    Parameters
    ----------
    name
        Module name inside the spcm_core package, e.g. "regs"

    Returns
    -------
        Loaded module
    """
    package_spec = importlib.util.find_spec("spcm_core")
    if package_spec is None or not package_spec.submodule_search_locations:
        raise ImportError("Package spcm_core is not installed.")
    module_path = Path(next(iter(package_spec.submodule_search_locations))) / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_spcm_core_{name}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {module_path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


regs = _load_module("regs")
spcerr = _load_module("spcerr")

# Export all public constants and helpers (e.g. KILO, MEGA_B) into this namespace
globals().update({key: val for key, val in vars(regs).items() if not key.startswith("_")})
globals().update({key: val for key, val in vars(spcerr).items() if not key.startswith("_")})
