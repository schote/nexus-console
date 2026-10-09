"""Auto-generate Code Reference pages from the console package source tree.

Strategy
--------
* Walk every .py file under src/console/, skipping vendor SDK bindings
  (spcm_control/spcm/) and __init__ modules.
* For modules that already have a hand-written narrative file under
  docs/reference/, leave the actual file untouched and register it in
  the nav.  The narrative file is expected to contain the
  ``:::`` mkdocstrings injection at its end.
* For all other modules, generate a minimal stub page via mkdocs_gen_files.
* Always write docs/reference/SUMMARY.md so literate-nav builds the nav.
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

# Repository root (three levels up from docs/scripts/)
ROOT = Path(__file__).parent.parent.parent
SRC = ROOT / "src"
PACKAGE = SRC / "console"
DOCS_REF = ROOT / "docs" / "reference"

# Vendor SDK bindings — excluded from user-facing docs
EXCLUDED_PREFIXES: tuple[str, ...] = ("console.spcm_control.spcm",)

nav = mkdocs_gen_files.Nav()

for py_path in sorted(PACKAGE.rglob("*.py")):
    # Build dotted module name: console.spcm_control.tx_device, …
    module_parts = py_path.relative_to(SRC).with_suffix("").parts
    module_name = ".".join(module_parts)

    # Skip excluded SDK bindings
    if any(module_name.startswith(exc) for exc in EXCLUDED_PREFIXES):
        continue

    # Skip __init__ files (package namespaces; no user-facing symbols)
    if module_parts[-1] == "__init__":
        continue

    # Build the path relative to docs/reference/
    # e.g. console/spcm_control/tx_device.py -> spcm_control/tx_device.md
    rel_parts = module_parts[1:]  # drop leading "console"
    doc_path = Path(*rel_parts).with_suffix(".md")
    full_doc_path = DOCS_REF / doc_path

    # Register in nav using human-readable section names
    nav[rel_parts] = str(doc_path)

    # Only generate a stub if no hand-written narrative exists
    if full_doc_path.exists():
        # Narrative file already present — nothing to generate
        continue

    # Generate minimal stub via mkdocs_gen_files virtual filesystem
    stub_path = Path("reference") / doc_path
    with mkdocs_gen_files.open(stub_path, "w") as fh:
        fh.write(f"::: {module_name}\n")

    mkdocs_gen_files.set_edit_path(stub_path, py_path.relative_to(ROOT))

# Generate a section index page so that links to reference/ resolve correctly
with mkdocs_gen_files.open("reference/index.md", "w") as fh:
    fh.write("# Code Reference\n\n")
    fh.write("Complete API documentation for all public modules in the `console` package.\n")

# Write the navigation file consumed by mkdocs-literate-nav
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as summary:
    summary.write("* [Overview](index.md)\n")
    summary.writelines(nav.build_literate_nav())
