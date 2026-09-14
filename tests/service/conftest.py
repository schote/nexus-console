"""Fixtures for the acquisition service tests."""
from pathlib import Path

import pytest


@pytest.fixture()
def nexus_runtime_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate the nexus runtime directory from a service running on the same machine."""
    monkeypatch.setenv("NEXUS_RUNTIME_DIR", str(tmp_path / "nexus"))
    return tmp_path / "nexus"
