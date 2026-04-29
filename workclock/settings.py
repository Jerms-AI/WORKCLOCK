"""settings.json: window/app preferences."""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {
    "always_on_top": True,
    "idle_threshold_minutes": 15,
    "remember_window_position": True,
    "window_position": None,
}


def _settings_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA env var is not set")
    return Path(appdata) / "WorkClock"


def _settings_file() -> Path:
    return _settings_dir() / "settings.json"


def read_settings() -> dict:
    sf = _settings_file()
    if not sf.exists():
        return dict(DEFAULTS)
    with open(sf, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    merged = dict(DEFAULTS)
    merged.update(loaded)
    return merged


def write_settings(settings: dict) -> None:
    sf = _settings_file()
    sf.parent.mkdir(parents=True, exist_ok=True)
    tmp = sf.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, sf)
