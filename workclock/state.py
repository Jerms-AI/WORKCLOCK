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


def _default_state() -> dict:
    return {"today": date.today().isoformat(), "projects": []}


def _apply_today_rollover(state: dict) -> dict:
    today = date.today().isoformat()
    if state.get("today") != today:
        state["today"] = today
        for p in state.get("projects", []):
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
    """Read state without taking the mutation lock. Applies today rollover.

    If the file is missing, returns a default state and does NOT write it.
    Today rollover, when triggered, writes the rolled-over state back.
    """
    sf = _state_file()
    if not sf.exists():
        return _default_state()
    with open(sf, "r", encoding="utf-8") as f:
        state = json.load(f)
    rolled = _apply_today_rollover(dict(state))
    if rolled != state:
        _write_state_unsafe(rolled)
    return rolled


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
