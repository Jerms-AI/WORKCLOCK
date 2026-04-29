"""Time_Worked.json: central log of completed sessions across ALL projects.

Lives in %APPDATA%\\WorkClock\\Time_Worked.json (alongside state.json) so the per-project
folders stay clean and nothing leaks via client transfers or git pushes.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

LOG_FILENAME = "Time_Worked.json"


def _log_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA env var is not set")
    return Path(appdata) / "WorkClock"


def log_path() -> Path:
    return _log_dir() / LOG_FILENAME


def ensure_log_exists() -> None:
    """Create an empty JSON array file if Time_Worked.json doesn't exist yet."""
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("[]\n", encoding="utf-8")


def append_session(
    project_name: str,
    start: datetime,
    stop: datetime,
    note: str | None,
) -> None:
    """Append a session entry to the central Time_Worked.json."""
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    if p.exists():
        try:
            entries = json.loads(p.read_text(encoding="utf-8") or "[]")
            if not isinstance(entries, list):
                entries = []
        except json.JSONDecodeError:
            entries = []
    else:
        entries = []

    entries.append({
        "project": project_name,
        "date": start.strftime("%Y-%m-%d"),
        "start": start.isoformat(),
        "stop": stop.isoformat(),
        "duration_seconds": max(0, int((stop - start).total_seconds())),
        "note": note if note else None,
    })

    p.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
