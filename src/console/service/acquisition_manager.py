"""Deprecated acquisition manager module."""
import warnings

_MOVED = {
    "AcquisitionControlManager": "nexus_service.acquisition_manager",
}

def __getattr__(name):
    if name in _MOVED:
        new_module = _MOVED[name]
        warnings.warn(
            f"Importing {name} from 'console.service.acquisition_manager' is deprecated "
            f"and will be removed in a future version. "
            f"Use 'from {new_module} import {name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        import importlib
        return getattr(importlib.import_module(new_module), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
