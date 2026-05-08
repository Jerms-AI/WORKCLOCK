"""state.json: source of truth for project list and running timers."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Callable

from filelock import FileLock


def _state_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA env var is not set")
    d = Path(appdata) / "WorkClock"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_file() -> Path:
    return _state_dir() / "state.json"


def _lock_file() -> Path:
    return _state_dir() / "state.lock"


PROJECT_DEFAULTS = {
    "subtitle": None,
    "rate": 0,
    "running": False,
    "paused": False,
    "started_at": None,
    "session_seconds": 0,
    "today_seconds": 0,
    "total_seconds": 0,
}


def _default_state() -> dict:
    return {"today": date.today().isoformat(), "projects": []}


def _ensure_project_fields(p: dict) -> None:
    """Backfill missing fields on legacy project entries (in-place)."""
    for k, v in PROJECT_DEFAULTS.items():
        p.setdefault(k, v)


def _apply_today_rollover(state: dict) -> dict:
    today = date.today().isoformat()
    rollover = state.get("today") != today
    if rollover:
        state["today"] = today
    for p in state.get("projects", []):
        _ensure_project_fields(p)
        if rollover:
            p["today_seconds"] = 0
    return state


def _write_state_unsafe(state: dict) -> None:
    """Write without taking the lock. Used internally and by tests."""
    target = _state_file()
    tmp = target.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)


def read_state() -> dict:
    """Read state without taking the mutation lock. Applies today rollover and
    backfills any missing project fields in the returned dict (not persisted).
    Persistence happens on the next mutate_state call.
    """
    sf = _state_file()
    if not sf.exists():
        return _default_state()
    with open(sf, "r", encoding="utf-8") as f:
        state = json.load(f)
    _apply_today_rollover(state)
    return state


def mutate_state(fn: Callable[[dict], None]) -> dict:
    """Take the lock, read, apply fn (in place), atomic-write, return new state."""
    with FileLock(str(_lock_file()), timeout=10):
        sf = _state_file()
        if sf.exists():
            with open(sf, "r", encoding="utf-8") as f:
                state = json.load(f)
        else:
            state = _default_state()
        _apply_today_rollover(state)
        fn(state)
        _write_state_unsafe(state)
        return state
