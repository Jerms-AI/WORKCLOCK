"""Billing logic: load WorkClock data, bucket outstanding work into
Friday-ending billing weeks, aggregate per-client paid vs outstanding.

Reads %APPDATA%\\WorkClock\\{Time_Worked.json,billing.json,state.json}
READ-ONLY. Never mutates source files.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

CLIENTS: dict[str, list[str]] = {
    "amd": ["ASANDRA_POC", "ASANDRA_APP", "SITEREVAMP"],
    "gloria": ["GLORIA"],
}

_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt(d: date) -> str:
    return f"{_MON[d.month]} {d.day}"


def _dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA env var is not set")
    return Path(appdata) / "WorkClock"


def _read_json(name: str, default):
    p = _dir() / name
    if not p.exists():
        return default
    txt = p.read_text(encoding="utf-8").strip()
    if not txt:
        return default
    return json.loads(txt)


def load_sessions() -> list[dict]:
    return _read_json("Time_Worked.json", [])


def load_payments() -> list[dict]:
    data = _read_json("billing.json", {"payments": []})
    return data.get("payments", []) if isinstance(data, dict) else []


def project_rate(project: str) -> int:
    state = _read_json("state.json", {"projects": []})
    for p in state.get("projects", []):
        if p.get("name") == project:
            return int(p.get("rate", 0))
    return 0


def week_end_friday(d: date) -> date:
    """The Friday on or after d (weekday(): Mon=0 .. Fri=4 .. Sun=6)."""
    return d + timedelta(days=(4 - d.weekday()) % 7)


def paid_week_count(period_start: date, period_end: date) -> int:
    """Number of 7-day weeks the paid invoice spans (inclusive, ceil)."""
    days = (period_end - period_start).days + 1
    return (days + 6) // 7
