"""Crash detection and long-session safety checks."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class RecoveryItem:
    name: str
    started_at: datetime
    proposed_stop_time: datetime


def check_recovery(
    state: dict,
    now: datetime,
    boot_time: datetime,
    state_mtime: datetime,
) -> list[RecoveryItem]:
    """Return one RecoveryItem per running project whose started_at predates
    boot_time or state_mtime — meaning the GUI couldn't have been recording."""
    items: list[RecoveryItem] = []
    for p in state.get("projects", []):
        if not p.get("running"):
            continue
        started_str = p.get("started_at")
        if not started_str:
            continue
        started = datetime.fromisoformat(started_str)
        if started < boot_time or started < state_mtime:
            proposed = max(boot_time, state_mtime)
            items.append(RecoveryItem(name=p["name"], started_at=started, proposed_stop_time=proposed))
    return items


def is_long_session(project: dict, now: datetime, threshold_hours: int = 12) -> bool:
    """True if this project has been running ≥ threshold_hours."""
    if not project.get("running"):
        return False
    started_str = project.get("started_at")
    if not started_str:
        return False
    started = datetime.fromisoformat(started_str)
    return (now - started) >= timedelta(hours=threshold_hours)
