"""Fixtures for the acquisition service tests."""
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture()
def runtime_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Isolate the nexus runtime directory from a service running on the same machine."""
    monkeypatch.setenv("NEXUS_RUNTIME_DIR", str(tmp_path / "nexus"))
    yield tmp_path / "nexus"
