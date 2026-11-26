"""Generate the API reference pages from the ``console`` and ``nexus_service`` package source trees.

The API reference is generated entirely from docstrings; no hand-written
content lives under ``docs/api_reference/``. Conceptual documentation belongs to
the System guide (``docs/system/``), which links into these pages.

* Walk every ``.py`` file under ``src/console/`` and ``src/nexus_service/``,
  skipping the vendor driver bindings (``spcm_control/spcm/``), the deprecated
  ``console.service`` aliases and ``__init__`` modules. Modules of ``console``
  are placed at the top level, those of ``nexus_service`` in its own section.
* Emit one virtual page per module containing a single ``:::`` mkdocstrings
  directive.
* Emit one page per hardware test script in ``tests/hardware/`` (see
  ``HARDWARE_TESTS``), which is on the mkdocstrings search path.
* Emit ``api_reference/index.md`` and ``api_reference/SUMMARY.md`` (consumed by
  mkdocs-literate-nav).
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

ROOT = Path(__file__).parent.parent.parent
SRC = ROOT / "src"
PACKAGES: tuple[str, ...] = ("console", "nexus_service")
REFERENCE = Path("api_reference")

# Hardware test scripts documented in the API reference, top-level modules of tests/hardware/
HARDWARE_TESTS: tuple[str, ...] = ("loopback",)

# Vendor driver bindings and deprecated aliases (moved to nexus_service) are excluded from the user-facing reference
EXCLUDED_PREFIXES: tuple[str, ...] = ("console.spcm_control.spcm", "console.service")

nav = mkdocs_gen_files.Nav()

for py_path in sorted(path for package in PACKAGES for path in (SRC / package).rglob("*.py")):
    module_parts = py_path.relative_to(SRC).with_suffix("").parts
    module_name = ".".join(module_parts)

    if any(module_name.startswith(exc) for exc in EXCLUDED_PREFIXES):
        continue
    if module_parts[-1] == "__init__":
        continue

    # e.g. console/spcm_control/tx_device.py -> api_reference/spcm_control/tx_device.md,
    # nexus_service/start_manager.py -> api_reference/nexus_service/start_manager.md
    rel_parts = module_parts[1:] if module_parts[0] == "console" else module_parts
    doc_path = Path(*rel_parts).with_suffix(".md")
    nav[rel_parts] = doc_path.as_posix()

    page_path = REFERENCE / doc_path
    with mkdocs_gen_files.open(page_path, "w") as fh:
        fh.write(f"::: {module_name}\n")
    mkdocs_gen_files.set_edit_path(page_path, py_path.relative_to(ROOT))

for module_name in HARDWARE_TESTS:
    # e.g. tests/hardware/loopback.py -> api_reference/hardware_tests/loopback.md
    rel_parts = ("hardware_tests", module_name)
    doc_path = Path(*rel_parts).with_suffix(".md")
    nav[rel_parts] = doc_path.as_posix()

    page_path = REFERENCE / doc_path
    with mkdocs_gen_files.open(page_path, "w") as fh:
        fh.write(f"::: {module_name}\n")
    mkdocs_gen_files.set_edit_path(page_path, Path("tests/hardware", module_name).with_suffix(".py"))

with mkdocs_gen_files.open(REFERENCE / "index.md", "w") as fh:
    fh.write(
        "# API reference\n\n"
        "Reference documentation of all public modules of the `console` package and the acquisition "
        "service `nexus_service`, "
        "generated from the source code docstrings. The hardware tests in `tests/hardware/` "
        "are listed under `hardware_tests`.\n\n"
        "For the architecture, hardware interplay and signal flow, see the "
        "[System guide](../system/overview.md).\n",
    )

with mkdocs_gen_files.open(REFERENCE / "SUMMARY.md", "w") as summary:
    summary.write("* [Overview](index.md)\n")
    summary.writelines(nav.build_literate_nav())
