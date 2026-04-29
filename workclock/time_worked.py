"""Time_Worked.json: per-project log of completed sessions, JSON array."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

LOG_FILENAME = "Time_Worked.json"


def log_path(project_dir: Path | str) -> Path:
    return Path(project_dir) / LOG_FILENAME


def ensure_log_exists(project_dir: Path | str) -> None:
    """Create an empty JSON array file if Time_Worked.json doesn't exist yet."""
    p = log_path(project_dir)
    if not p.exists():
        p.write_text("[]\n", encoding="utf-8")


def append_session(
    project_dir: Path | str,
    project_name: str,
    start: datetime,
    stop: datetime,
    note: str | None,
) -> None:
    """Append a session entry to Time_Worked.json. Creates the file if absent."""
    p = log_path(project_dir)
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
