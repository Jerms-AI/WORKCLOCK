import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_appdata(tmp_path, monkeypatch):
    """Redirect APPDATA to a temp directory for state/settings tests."""
    appdata = tmp_path / "AppData"
    appdata.mkdir()
    monkeypatch.setenv("APPDATA", str(appdata))
    return appdata
