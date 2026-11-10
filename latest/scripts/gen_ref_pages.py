"""Generate the API reference pages from the ``console`` package source tree.

The API reference is generated entirely from docstrings; no hand-written
content lives under ``docs/reference/``. Conceptual documentation belongs to
the System guide (``docs/system/``), which links into these pages.

* Walk every ``.py`` file under ``src/console/``, skipping the vendor driver
  bindings (``spcm_control/spcm/``) and ``__init__`` modules.
* Emit one virtual page per module containing a single ``:::`` mkdocstrings
  directive.
* Emit ``reference/index.md`` and ``reference/SUMMARY.md`` (consumed by
  mkdocs-literate-nav).
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

ROOT = Path(__file__).parent.parent.parent
SRC = ROOT / "src"
PACKAGE = SRC / "console"

# Vendor driver bindings are excluded from the user-facing reference
EXCLUDED_PREFIXES: tuple[str, ...] = ("console.spcm_control.spcm",)

nav = mkdocs_gen_files.Nav()

for py_path in sorted(PACKAGE.rglob("*.py")):
    module_parts = py_path.relative_to(SRC).with_suffix("").parts
    module_name = ".".join(module_parts)

    if any(module_name.startswith(exc) for exc in EXCLUDED_PREFIXES):
        continue
    if module_parts[-1] == "__init__":
        continue

    # e.g. console/spcm_control/tx_device.py -> reference/spcm_control/tx_device.md
    rel_parts = module_parts[1:]
    doc_path = Path(*rel_parts).with_suffix(".md")
    nav[rel_parts] = doc_path.as_posix()

    page_path = Path("reference") / doc_path
    with mkdocs_gen_files.open(page_path, "w") as fh:
        fh.write(f"::: {module_name}\n")
    mkdocs_gen_files.set_edit_path(page_path, py_path.relative_to(ROOT))

with mkdocs_gen_files.open("reference/index.md", "w") as fh:
    fh.write(
        "# API reference\n\n"
        "Reference documentation of all public modules of the `console` package, "
        "generated from the source code docstrings.\n\n"
        "For the architecture, hardware interplay and signal flow, see the "
        "[System guide](../system/overview.md).\n",
    )

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as summary:
    summary.write("* [Overview](index.md)\n")
    summary.writelines(nav.build_literate_nav())
