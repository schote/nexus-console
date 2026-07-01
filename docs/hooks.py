"""MkDocs build hooks — suppress non-fatal griffe log messages.

griffe emits WARNING/ERROR messages for:
- docstring parameters written as ``name, optional`` (no colon/type)
  which the NumPy parser splits into two names, one being "optional"
- line_profiler.profile alias resolution (C extension, not statically
  analysable by griffe even when the package is installed)

These messages do not affect the rendered output.

The suppression is applied at *module import time* (not inside an event
handler) so it takes effect before griffe processes any source file,
regardless of which MkDocs version or event order is in use.
"""
import logging

# ── Module-level: runs when hooks.py is imported, before any event ──────────
logging.getLogger("griffe").setLevel(logging.CRITICAL)


# ── Belt-and-suspenders: re-apply in the earliest events that fire ───────────

def on_startup(**kwargs: object) -> None:
    logging.getLogger("griffe").setLevel(logging.CRITICAL)


def on_config(config: object, **kwargs: object) -> object:
    logging.getLogger("griffe").setLevel(logging.CRITICAL)
    return config


def on_pre_build(config: object, **kwargs: object) -> None:
    logging.getLogger("griffe").setLevel(logging.CRITICAL)


def on_pre_page(page: object, **kwargs: object) -> object:
    logging.getLogger("griffe").setLevel(logging.CRITICAL)
    return page
