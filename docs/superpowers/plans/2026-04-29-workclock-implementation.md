# WorkClock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tiny always-on-top time tracker for multi-project work. Users click a colored dot per project to start/stop timers; sessions append to `hours.md` at each project root. Claude (the assistant) controls the same state by editing `state.json` directly via file tools — no CLI surface.

**Architecture:** Single Python GUI process using `pywebview` (system webview, not Chromium). HTML/CSS/JS renders the window; Python owns file I/O. `state.json` in `%APPDATA%\WorkClock\` is the single source of truth. The GUI watches state.json with `watchdog` and re-renders when it changes — so Claude's edits and button clicks both flow through the same path.

**Tech Stack:** Python 3.13 (Windows-side), `pywebview`, `watchdog`, `filelock`, `psutil`, `pytest`. UI: vanilla HTML/CSS/JS, monospace digital-readout aesthetic (amber on near-black).

**Spec:** `docs/superpowers/specs/2026-04-29-workclock-design.md`

---

## Pre-flight

**Python:** Windows-side Python 3.13 already installed at `C:\Users\Xliminal\AppData\Local\Programs\Python\Python313\python.exe`.

**Path shorthand used throughout this plan:**
- `PYWIN` = `/mnt/c/Users/Xliminal/AppData/Local/Programs/Python/Python313/python.exe`
- `PROJECT` = `/mnt/c/Users/Xliminal/Code/PersonalProjects/WorkClock`
- After Task 2, replace `PYWIN` with the venv Python: `$PROJECT/venv/Scripts/python.exe`

**Working directory for all commands:** `cd "$PROJECT"`.

**WSL path note:** all file operations from WSL use `/mnt/c/Users/Xliminal/...`. The Python code itself stores Windows-style paths (`C:\...` and `\\wsl$\...`).

---

## File Structure

```
WorkClock/
├── README.md                  # Schema reference, doubles as Claude's contract doc
├── WorkClock.bat              # Launcher: activates venv, starts pythonw main.py
├── main.py                    # Entry: pywebview window + watchdog observer + JS API
├── requirements.txt
├── .gitignore
├── workclock/
│   ├── __init__.py
│   ├── state.py               # state.json read/write (atomic + filelock), today rollover
│   ├── settings.py            # settings.json read/write
│   ├── paths.py               # normalize Linux/WSL/Windows → Windows path
│   ├── hours.py               # append to hours.md, format durations, format times
│   ├── idle.py                # GetLastInputInfo via ctypes
│   └── recovery.py            # crash + 12hr safety detection
├── ui/
│   ├── window.html            # one-page GUI shell
│   ├── style.css              # amber-on-black digital readout
│   └── app.js                 # rows, buttons, polling, JS-to-Python bridge
├── tests/
│   ├── conftest.py            # tmp APPDATA fixture
│   ├── test_paths.py
│   ├── test_hours.py
│   ├── test_state.py
│   └── test_recovery.py
└── docs/
    └── superpowers/
        ├── specs/2026-04-29-workclock-design.md
        └── plans/2026-04-29-workclock-implementation.md
```

App data (not in repo): `%APPDATA%\WorkClock\` → `state.json`, `settings.json`, `state.lock`, `gui.lock`.

---

## Task 1: Scaffold project, init git, commit spec

**Files:**
- Create: `.gitignore`
- Create: `README.md` (placeholder; full content in Task 15)
- Init: git repo at `$PROJECT`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
venv/
__pycache__/
*.pyc
.pytest_cache/
.vscode/
.idea/
*.log
```

- [ ] **Step 2: Create placeholder `README.md`**

```markdown
# WorkClock

A tiny always-on-top time tracker for multi-project work.

See `docs/superpowers/specs/2026-04-29-workclock-design.md` for the full design.
Full README contents land in the final implementation task.
```

- [ ] **Step 3: Initialize git and make first commit**

```bash
cd "$PROJECT"
git init
git add .gitignore README.md docs/
git commit -m "chore: scaffold WorkClock with spec and design plan"
```

Expected: one commit on main/master, spec + plan + README + .gitignore tracked.

---

## Task 2: Create venv, install dependencies

**Files:**
- Create: `requirements.txt`
- Create: `venv/` (excluded from git)

- [ ] **Step 1: Write `requirements.txt`**

```
pywebview==5.3
watchdog==4.0.2
filelock==3.15.4
psutil==6.0.0
pytest==8.3.3
```

- [ ] **Step 2: Create venv with Windows Python**

```bash
cd "$PROJECT"
/mnt/c/Users/Xliminal/AppData/Local/Programs/Python/Python313/python.exe -m venv venv
```

Expected: `venv/Scripts/python.exe` exists.

- [ ] **Step 3: Install dependencies**

```bash
./venv/Scripts/python.exe -m pip install --upgrade pip
./venv/Scripts/python.exe -m pip install -r requirements.txt
```

Expected: pywebview, watchdog, filelock, psutil, pytest installed without error.

- [ ] **Step 4: Verify pytest works**

```bash
./venv/Scripts/python.exe -m pytest --version
```

Expected: prints pytest 8.x version.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "chore: add requirements.txt and create venv"
```

---

## Task 3: Path normalization (paths.py) — TDD

**Files:**
- Create: `workclock/__init__.py` (empty)
- Create: `workclock/paths.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: Write empty package files**

```python
# workclock/__init__.py
```

```python
# tests/__init__.py
```

- [ ] **Step 2: Write `tests/conftest.py`**

```python
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
```

- [ ] **Step 3: Write failing tests for path normalization**

```python
# tests/test_paths.py
import pytest

from workclock.paths import normalize_path


def test_windows_path_passthrough():
    assert normalize_path(r"C:\foo\bar") == r"C:\foo\bar"


def test_windows_path_forward_slashes_normalized_to_backslashes():
    assert normalize_path("C:/foo/bar") == r"C:\foo\bar"


def test_mnt_c_translates_to_windows_drive():
    assert normalize_path("/mnt/c/foo/bar") == r"C:\foo\bar"


def test_mnt_d_translates_to_windows_drive():
    assert normalize_path("/mnt/d/projects/x") == r"D:\projects\x"


def test_home_translates_to_wsl_unc():
    assert normalize_path("/home/jermsai/Code/X") == r"\\wsl$\Ubuntu\home\jermsai\Code\X"


def test_root_linux_path_translates_to_wsl_unc():
    assert normalize_path("/etc/hosts") == r"\\wsl$\Ubuntu\etc\hosts"


def test_trailing_slash_stripped():
    assert normalize_path("/mnt/c/foo/") == r"C:\foo"


def test_unknown_format_raises():
    with pytest.raises(ValueError):
        normalize_path("relative/path")
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd "$PROJECT"
./venv/Scripts/python.exe -m pytest tests/test_paths.py -v
```

Expected: ImportError (module doesn't exist) or all FAIL.

- [ ] **Step 5: Implement `workclock/paths.py`**

```python
"""Normalize project paths to Windows-readable form for storage."""
from __future__ import annotations

import re

WSL_DISTRO = "Ubuntu"


def normalize_path(input_path: str) -> str:
    """Accept Linux/WSL/Windows paths; return Windows-readable form.

    Examples:
        C:\\foo\\bar      -> C:\\foo\\bar
        C:/foo/bar        -> C:\\foo\\bar
        /mnt/c/foo/bar    -> C:\\foo\\bar
        /home/jermsai/X   -> \\\\wsl$\\Ubuntu\\home\\jermsai\\X
    """
    p = input_path.rstrip("/").rstrip("\\")

    # Windows drive (C:\ or C:/)
    win_drive = re.match(r"^([A-Za-z]):[/\\](.*)$", p)
    if win_drive:
        drive, rest = win_drive.groups()
        return f"{drive.upper()}:\\" + rest.replace("/", "\\")

    # WSL mount: /mnt/c/... -> C:\...
    mnt = re.match(r"^/mnt/([a-z])(/(.*))?$", p)
    if mnt:
        drive = mnt.group(1).upper()
        rest = mnt.group(3) or ""
        return f"{drive}:\\" + rest.replace("/", "\\")

    # Absolute Linux path: /home/... -> \\wsl$\Ubuntu\home\...
    if p.startswith("/"):
        rest = p.lstrip("/").replace("/", "\\")
        return f"\\\\wsl$\\{WSL_DISTRO}\\{rest}"

    raise ValueError(f"Cannot normalize path: {input_path!r}")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
./venv/Scripts/python.exe -m pytest tests/test_paths.py -v
```

Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
git add workclock/__init__.py workclock/paths.py tests/__init__.py tests/conftest.py tests/test_paths.py
git commit -m "feat: path normalization for Linux/WSL/Windows inputs"
```

---

## Task 4: Duration & time formatting (hours.py — formatters only) — TDD

**Files:**
- Create: `workclock/hours.py` (formatters only this task; append in Task 5)
- Create: `tests/test_hours.py`

- [ ] **Step 1: Write failing tests for formatters**

```python
# tests/test_hours.py
from datetime import datetime

from workclock.hours import format_duration, format_time


def test_duration_minutes_only():
    assert format_duration(45 * 60) == "45m"


def test_duration_one_minute():
    assert format_duration(60) == "1m"


def test_duration_zero_seconds_collapses_to_zero_m():
    assert format_duration(0) == "0m"


def test_duration_under_minute_truncates():
    assert format_duration(45) == "0m"


def test_duration_one_hour_clean():
    assert format_duration(60 * 60) == "1h 0m"


def test_duration_two_hours_twenty_eight_minutes():
    assert format_duration(2 * 3600 + 28 * 60) == "2h 28m"


def test_duration_seconds_truncated_not_rounded():
    assert format_duration(2 * 3600 + 28 * 60 + 59) == "2h 28m"


def test_format_time_local():
    dt = datetime(2026, 4, 29, 9, 5)
    assert format_time(dt) == "09:05"


def test_format_time_midnight():
    dt = datetime(2026, 4, 29, 0, 0)
    assert format_time(dt) == "00:00"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/Scripts/python.exe -m pytest tests/test_hours.py -v
```

Expected: ImportError or all FAIL.

- [ ] **Step 3: Implement formatters in `workclock/hours.py`**

```python
"""hours.md per-project log: formatters and append logic."""
from __future__ import annotations

from datetime import datetime


def format_duration(seconds: int) -> str:
    """Format a duration as 'Xh Ym' or 'Ym' (seconds truncated)."""
    total_minutes = seconds // 60
    hours, minutes = divmod(total_minutes, 60)
    if hours == 0:
        return f"{minutes}m"
    return f"{hours}h {minutes}m"


def format_time(dt: datetime) -> str:
    """Format a datetime as 'HH:MM' (24-hour, local time assumed)."""
    return dt.strftime("%H:%M")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./venv/Scripts/python.exe -m pytest tests/test_hours.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add workclock/hours.py tests/test_hours.py
git commit -m "feat: duration and time formatters for hours.md"
```

---

## Task 5: Append session to hours.md — TDD

**Files:**
- Modify: `workclock/hours.py` (add `append_session`)
- Modify: `tests/test_hours.py` (add append tests)

- [ ] **Step 1: Add failing tests for append_session**

Append to `tests/test_hours.py`:

```python
from datetime import datetime
from pathlib import Path

from workclock.hours import append_session


def test_creates_file_with_header_when_missing(tmp_path):
    project_dir = tmp_path / "Gloria"
    project_dir.mkdir()
    start = datetime(2026, 4, 29, 9, 15)
    stop = datetime(2026, 4, 29, 11, 43)

    append_session(project_dir, "Gloria", start, stop, note=None)

    content = (project_dir / "hours.md").read_text()
    assert content.startswith("# Hours — Gloria\n")
    assert "## 2026-04-29" in content
    assert "- 09:15–11:43 (2h 28m)" in content


def test_appends_to_existing_day_section(tmp_path):
    project_dir = tmp_path / "Gloria"
    project_dir.mkdir()
    (project_dir / "hours.md").write_text(
        "# Hours — Gloria\n\n## 2026-04-29\n- 09:15–11:43 (2h 28m)\n"
    )

    append_session(
        project_dir,
        "Gloria",
        datetime(2026, 4, 29, 13, 30),
        datetime(2026, 4, 29, 15, 0),
        note=None,
    )

    content = (project_dir / "hours.md").read_text()
    lines = content.splitlines()
    assert "- 09:15–11:43 (2h 28m)" in lines
    assert "- 13:30–15:00 (1h 30m)" in lines
    # Both bullets under the same ## 2026-04-29 section, no duplicate header
    assert content.count("## 2026-04-29") == 1


def test_prepends_new_day_section_above_existing(tmp_path):
    project_dir = tmp_path / "Gloria"
    project_dir.mkdir()
    (project_dir / "hours.md").write_text(
        "# Hours — Gloria\n\n## 2026-04-28\n- 10:00–12:15 (2h 15m)\n"
    )

    append_session(
        project_dir,
        "Gloria",
        datetime(2026, 4, 29, 9, 15),
        datetime(2026, 4, 29, 11, 43),
        note=None,
    )

    content = (project_dir / "hours.md").read_text()
    # New day appears above older day
    apr29_idx = content.index("## 2026-04-29")
    apr28_idx = content.index("## 2026-04-28")
    assert apr29_idx < apr28_idx


def test_note_appended_with_em_dash(tmp_path):
    project_dir = tmp_path / "Gloria"
    project_dir.mkdir()

    append_session(
        project_dir,
        "Gloria",
        datetime(2026, 4, 29, 9, 15),
        datetime(2026, 4, 29, 11, 43),
        note="auth refactor",
    )

    content = (project_dir / "hours.md").read_text()
    assert "- 09:15–11:43 (2h 28m) — auth refactor" in content


def test_session_crossing_midnight_filed_under_start_date(tmp_path):
    project_dir = tmp_path / "Gloria"
    project_dir.mkdir()

    append_session(
        project_dir,
        "Gloria",
        datetime(2026, 4, 28, 23, 30),
        datetime(2026, 4, 29, 0, 45),
        note=None,
    )

    content = (project_dir / "hours.md").read_text()
    assert "## 2026-04-28" in content
    assert "## 2026-04-29" not in content
    assert "- 23:30–00:45 (1h 15m)" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/Scripts/python.exe -m pytest tests/test_hours.py -v
```

Expected: 5 new tests fail (`AttributeError: append_session`).

- [ ] **Step 3: Implement `append_session` in `workclock/hours.py`**

Append to `workclock/hours.py`:

```python
from pathlib import Path


def append_session(
    project_dir: Path | str,
    display_name: str,
    start: datetime,
    stop: datetime,
    note: str | None,
) -> None:
    """Append a session bullet to hours.md at project_dir.

    File created with `# Hours — {display_name}` header if absent.
    Session is filed under the START date (handles midnight-crossing).
    Day section is created (prepended) if it doesn't exist.
    """
    project_dir = Path(project_dir)
    hours_file = project_dir / "hours.md"

    duration_seconds = int((stop - start).total_seconds())
    bullet = f"- {format_time(start)}–{format_time(stop)} ({format_duration(duration_seconds)})"
    if note:
        bullet += f" — {note}"
    day_header = f"## {start.strftime('%Y-%m-%d')}"

    if not hours_file.exists():
        content = f"# Hours — {display_name}\n\n{day_header}\n{bullet}\n"
        hours_file.write_text(content, encoding="utf-8")
        return

    text = hours_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)

    # Find the day header line, if any
    day_idx = None
    for i, line in enumerate(lines):
        if line.strip() == day_header:
            day_idx = i
            break

    if day_idx is not None:
        # Insert bullet at end of this day's section (before next ## or EOF)
        insert_at = len(lines)
        for j in range(day_idx + 1, len(lines)):
            if lines[j].startswith("## "):
                insert_at = j
                break
        # Skip blank lines at the tail of the section
        while insert_at > day_idx + 1 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        lines.insert(insert_at, bullet)
    else:
        # Prepend new day section above the first existing ## section
        first_day_idx = None
        for i, line in enumerate(lines):
            if line.startswith("## "):
                first_day_idx = i
                break
        new_section = [day_header, bullet, ""]
        if first_day_idx is not None:
            for offset, new_line in enumerate(new_section):
                lines.insert(first_day_idx + offset, new_line)
        else:
            # No existing day sections; append after the header
            if lines and lines[-1].strip() != "":
                lines.append("")
            lines.extend(new_section[:-1])  # no trailing blank

    hours_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./venv/Scripts/python.exe -m pytest tests/test_hours.py -v
```

Expected: all 14 tests pass (9 formatter + 5 append).

- [ ] **Step 5: Commit**

```bash
git add workclock/hours.py tests/test_hours.py
git commit -m "feat: append session bullets to hours.md with day-section logic"
```

---

## Task 6: state.json read/write (state.py) — TDD

**Files:**
- Create: `workclock/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests for state module**

```python
# tests/test_state.py
import json
from datetime import date

from workclock import state as state_mod


def test_read_state_returns_default_when_missing(tmp_appdata):
    s = state_mod.read_state()
    assert s == {"today": date.today().isoformat(), "projects": []}


def test_read_state_round_trips(tmp_appdata):
    initial = {
        "today": "2026-04-29",
        "projects": [
            {
                "name": "GLORIA",
                "path": r"C:\Users\Xliminal\Code\PersonalProjects\Gloria",
                "running": False,
                "started_at": None,
                "today_seconds": 0,
            }
        ],
    }
    state_mod._write_state_unsafe(initial)
    s = state_mod.read_state()
    assert s == initial


def test_today_rollover_resets_today_seconds(tmp_appdata):
    initial = {
        "today": "2026-04-28",  # yesterday
        "projects": [
            {
                "name": "GLORIA",
                "path": r"C:\X",
                "running": False,
                "started_at": None,
                "today_seconds": 8100,
            }
        ],
    }
    state_mod._write_state_unsafe(initial)

    s = state_mod.read_state()
    assert s["today"] == date.today().isoformat()
    assert s["projects"][0]["today_seconds"] == 0


def test_mutate_state_applies_function_atomically(tmp_appdata):
    def add_project(s):
        s["projects"].append(
            {
                "name": "WTF_IS_PHYSICS",
                "path": r"\\wsl$\Ubuntu\home\jermsai\Code\WTF_Is_Physics",
                "running": False,
                "started_at": None,
                "today_seconds": 0,
            }
        )

    new_state = state_mod.mutate_state(add_project)
    assert len(new_state["projects"]) == 1
    assert new_state["projects"][0]["name"] == "WTF_IS_PHYSICS"

    # File reflects the change
    on_disk = state_mod.read_state()
    assert on_disk["projects"][0]["name"] == "WTF_IS_PHYSICS"


def test_atomic_write_no_partial_file_on_disk(tmp_appdata):
    # Sanity check: the .tmp file should not linger after a successful write
    state_mod.mutate_state(lambda s: s["projects"].append(
        {"name": "X", "path": r"C:\x", "running": False, "started_at": None, "today_seconds": 0}
    ))
    appdata = tmp_appdata / "WorkClock"
    assert (appdata / "state.json").exists()
    assert not (appdata / "state.json.tmp").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/Scripts/python.exe -m pytest tests/test_state.py -v
```

Expected: ImportError or all FAIL.

- [ ] **Step 3: Implement `workclock/state.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./venv/Scripts/python.exe -m pytest tests/test_state.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add workclock/state.py tests/test_state.py
git commit -m "feat: state.json read/mutate with atomic write, filelock, today rollover"
```

---

## Task 7: Crash & long-session recovery (recovery.py) — TDD

**Files:**
- Create: `workclock/recovery.py`
- Create: `tests/test_recovery.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_recovery.py
from datetime import datetime, timedelta, timezone

from workclock.recovery import RecoveryItem, check_recovery, is_long_session


def _project(name: str, running: bool, started_at: str | None) -> dict:
    return {
        "name": name,
        "path": r"C:\X",
        "running": running,
        "started_at": started_at,
        "today_seconds": 0,
    }


def test_no_running_projects_no_recovery():
    state = {"today": "2026-04-29", "projects": [_project("A", False, None)]}
    items = check_recovery(state, now=datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
                            boot_time=datetime(2026, 4, 29, 8, 0, tzinfo=timezone.utc),
                            state_mtime=datetime(2026, 4, 29, 11, 50, tzinfo=timezone.utc))
    assert items == []


def test_started_before_boot_triggers_recovery():
    started = datetime(2026, 4, 28, 22, 0, tzinfo=timezone.utc).isoformat()
    state = {"today": "2026-04-29", "projects": [_project("A", True, started)]}
    items = check_recovery(state,
                            now=datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
                            boot_time=datetime(2026, 4, 29, 8, 0, tzinfo=timezone.utc),
                            state_mtime=datetime(2026, 4, 29, 11, 50, tzinfo=timezone.utc))
    assert len(items) == 1
    assert items[0].name == "A"
    # proposed_stop_time = max(boot, mtime) = mtime
    assert items[0].proposed_stop_time == datetime(2026, 4, 29, 11, 50, tzinfo=timezone.utc)


def test_started_after_boot_and_mtime_no_recovery():
    started = datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc).isoformat()
    state = {"today": "2026-04-29", "projects": [_project("A", True, started)]}
    items = check_recovery(state,
                            now=datetime(2026, 4, 29, 9, 30, tzinfo=timezone.utc),
                            boot_time=datetime(2026, 4, 29, 8, 0, tzinfo=timezone.utc),
                            state_mtime=datetime(2026, 4, 29, 8, 55, tzinfo=timezone.utc))
    assert items == []


def test_is_long_session_true_after_12_hours():
    started = datetime(2026, 4, 29, 0, 0, tzinfo=timezone.utc).isoformat()
    project = _project("A", True, started)
    assert is_long_session(project, now=datetime(2026, 4, 29, 13, 0, tzinfo=timezone.utc))


def test_is_long_session_false_under_12_hours():
    started = datetime(2026, 4, 29, 6, 0, tzinfo=timezone.utc).isoformat()
    project = _project("A", True, started)
    assert not is_long_session(project, now=datetime(2026, 4, 29, 13, 0, tzinfo=timezone.utc))


def test_is_long_session_false_when_not_running():
    project = _project("A", False, None)
    assert not is_long_session(project, now=datetime(2026, 4, 29, 13, 0, tzinfo=timezone.utc))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/Scripts/python.exe -m pytest tests/test_recovery.py -v
```

Expected: ImportError or all FAIL.

- [ ] **Step 3: Implement `workclock/recovery.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./venv/Scripts/python.exe -m pytest tests/test_recovery.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add workclock/recovery.py tests/test_recovery.py
git commit -m "feat: crash recovery and 12-hour long-session detection"
```

---

## Task 8: Settings module (settings.py) — TDD

**Files:**
- Create: `workclock/settings.py`
- Modify: `tests/test_state.py` (add settings tests, or new file)

For separation of concerns, use a new test file.

**Files:**
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_settings.py
from workclock import settings as settings_mod


def test_read_settings_returns_defaults_when_missing(tmp_appdata):
    s = settings_mod.read_settings()
    assert s == {
        "always_on_top": True,
        "idle_threshold_minutes": 15,
        "remember_window_position": True,
        "window_position": None,
    }


def test_write_then_read_round_trips(tmp_appdata):
    settings_mod.write_settings({
        "always_on_top": False,
        "idle_threshold_minutes": 30,
        "remember_window_position": True,
        "window_position": [100, 200],
    })
    s = settings_mod.read_settings()
    assert s["always_on_top"] is False
    assert s["idle_threshold_minutes"] == 30
    assert s["window_position"] == [100, 200]


def test_partial_settings_merged_with_defaults(tmp_appdata):
    # User-edited file with only some keys should fill in defaults for missing
    import json
    from workclock.settings import _settings_file
    _settings_file().parent.mkdir(parents=True, exist_ok=True)
    _settings_file().write_text(json.dumps({"idle_threshold_minutes": 5}))
    s = settings_mod.read_settings()
    assert s["idle_threshold_minutes"] == 5
    assert s["always_on_top"] is True  # default preserved
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/Scripts/python.exe -m pytest tests/test_settings.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `workclock/settings.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./venv/Scripts/python.exe -m pytest tests/test_settings.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add workclock/settings.py tests/test_settings.py
git commit -m "feat: settings.json read/write with default merge"
```

---

## Task 9: Idle detection (idle.py) — Windows API wrapper

This module wraps `GetLastInputInfo` from `user32.dll`. It can't be unit-tested without mocking ctypes, so we do a smoke-test verification step.

**Files:**
- Create: `workclock/idle.py`

- [ ] **Step 1: Implement `workclock/idle.py`**

```python
"""Windows idle-time detection via GetLastInputInfo."""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_idle_seconds() -> int:
    """Seconds since last keyboard or mouse input on Windows.

    Returns 0 on non-Windows platforms or if the call fails.
    """
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0
        millis_now = ctypes.windll.kernel32.GetTickCount()
        return (millis_now - info.dwTime) // 1000
    except (OSError, AttributeError):
        return 0
```

- [ ] **Step 2: Smoke-test from the venv Python**

```bash
./venv/Scripts/python.exe -c "from workclock.idle import get_idle_seconds; print('idle seconds:', get_idle_seconds())"
```

Expected: prints `idle seconds: <small number>` (e.g., 0–5 immediately after running). If you wait and don't move the mouse for 10s, then run, expect a higher number.

- [ ] **Step 3: Commit**

```bash
git add workclock/idle.py
git commit -m "feat: Windows idle-time detection via GetLastInputInfo"
```

---

## Task 10: UI shell — HTML

**Files:**
- Create: `ui/window.html`

- [ ] **Step 1: Write `ui/window.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>WorkClock</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <header id="topbar">
    <span class="title">WORKCLOCK</span>
    <div class="topbar-actions">
      <button id="add-btn" class="icon-btn" title="Ask Claude to add a project" aria-label="Add project">+</button>
      <button id="settings-btn" class="icon-btn" title="Settings" aria-label="Settings">⚙</button>
    </div>
  </header>

  <main id="rows"></main>

  <section id="settings-panel" hidden>
    <div class="setting">
      <label>
        <input type="checkbox" id="setting-always-on-top" />
        Always on top
      </label>
    </div>
    <div class="setting">
      <label>
        Idle nudge threshold (minutes):
        <input type="number" id="setting-idle-threshold" min="1" max="240" />
      </label>
    </div>
    <div class="setting">
      <label>
        <input type="checkbox" id="setting-remember-position" />
        Remember window position
      </label>
    </div>
    <div class="setting">
      <button id="setting-reset-position" class="text-btn">Reset to top-right</button>
    </div>
    <div class="setting setting-actions">
      <button id="settings-close" class="text-btn">Close</button>
    </div>
  </section>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit (CSS and JS land in next tasks)**

```bash
git add ui/window.html
git commit -m "feat: window.html shell with topbar, rows container, settings panel"
```

---

## Task 11: UI styling — CSS (digital readout)

**Files:**
- Create: `ui/style.css`

- [ ] **Step 1: Write `ui/style.css`**

```css
:root {
  --bg: #0a0a0a;
  --fg: #ffb347;
  --fg-dim: #ffb34766;
  --row-divider: #ffb34722;
  --green: #4ade80;
  --red: #ef4444;
  --warn: #facc15;
  --font-mono: "JetBrains Mono", "IBM Plex Mono", "Cascadia Mono", "Consolas", monospace;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  background: var(--bg);
  color: var(--fg);
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.4;
  user-select: none;
  -webkit-user-select: none;
  overflow: hidden;
}

#topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--row-divider);
  -webkit-app-region: drag;  /* draggable window region */
}

#topbar .title {
  font-size: 11px;
  letter-spacing: 0.2em;
  color: var(--fg-dim);
}

.topbar-actions {
  display: flex;
  gap: 4px;
  -webkit-app-region: no-drag;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--fg-dim);
  font-size: 16px;
  width: 24px;
  height: 24px;
  cursor: pointer;
  border-radius: 4px;
}

.icon-btn:hover {
  color: var(--fg);
  background: var(--row-divider);
}

#rows {
  padding: 4px 0;
}

.row {
  display: grid;
  grid-template-columns: 1fr auto 40px;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--row-divider);
  -webkit-app-region: no-drag;
}

.row:last-child {
  border-bottom: none;
}

.row .name {
  font-weight: 700;
  letter-spacing: 0.05em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row .counter {
  font-variant-numeric: tabular-nums;
  font-size: 18px;
  color: var(--fg);
}

.row.running .counter {
  color: var(--fg);
}

.row.idle-dim .counter {
  color: var(--fg-dim);
  transition: color 0.4s ease;
}

.row.long-session {
  border-left: 2px solid var(--warn);
}

.row.recovery {
  background: #1a1208;
}

.dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  border: none;
  display: block;
  margin-left: auto;
}

.dot.green {
  background: var(--green);
  box-shadow: 0 0 6px #4ade8088;
}

.dot.red {
  background: var(--red);
  box-shadow: 0 0 6px #ef444488;
}

.dot.red.pulsing {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 6px #ef444488; opacity: 1; }
  50% { box-shadow: 0 0 14px #ef4444cc; opacity: 0.6; }
}

.note-input-wrap {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0 0 0;
}

.note-input {
  flex: 1;
  background: transparent;
  border: 1px solid var(--row-divider);
  color: var(--fg);
  padding: 4px 8px;
  font-family: var(--font-mono);
  font-size: 13px;
  outline: none;
}

.note-input:focus {
  border-color: var(--fg);
}

.text-btn {
  background: transparent;
  border: 1px solid var(--row-divider);
  color: var(--fg);
  padding: 3px 10px;
  font-family: var(--font-mono);
  font-size: 12px;
  cursor: pointer;
}

.text-btn:hover {
  background: var(--row-divider);
}

#settings-panel {
  border-top: 1px solid var(--row-divider);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #0e0e0e;
}

#settings-panel .setting {
  font-size: 13px;
  color: var(--fg-dim);
}

#settings-panel input[type="number"] {
  width: 60px;
  background: var(--bg);
  border: 1px solid var(--row-divider);
  color: var(--fg);
  padding: 2px 6px;
  font-family: var(--font-mono);
}

.setting-actions {
  display: flex;
  justify-content: flex-end;
}

.recovery-actions {
  display: flex;
  gap: 6px;
  grid-column: 1 / -1;
  padding-top: 6px;
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/style.css
git commit -m "feat: amber-on-black digital-readout styling"
```

---

## Task 12: UI behavior — JavaScript (rendering, button handlers, polling)

**Files:**
- Create: `ui/app.js`

- [ ] **Step 1: Write `ui/app.js`**

```javascript
// app.js — renders rows from state, handles button clicks via pywebview API

let state = { today: null, projects: [] };
let idleSeconds = 0;
let idleThreshold = 15 * 60;
let openNoteFor = null;  // project name with an open note input
let pendingTrim = {};    // { projectName: trimTimestampISO }

function fmtCounter(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function elapsedSecondsForProject(p) {
  if (!p.running || !p.started_at) return p.today_seconds;
  const startMs = new Date(p.started_at).getTime();
  const sessionSecs = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
  return p.today_seconds + sessionSecs;
}

function render() {
  const rowsEl = document.getElementById('rows');
  rowsEl.innerHTML = '';

  if (state.projects.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'row';
    empty.innerHTML = '<span class="name" style="color: var(--fg-dim); font-weight: 400;">No projects. Ask Claude to add one.</span>';
    rowsEl.appendChild(empty);
    return;
  }

  for (const p of state.projects) {
    const row = document.createElement('div');
    row.className = 'row';
    if (p.running) row.classList.add('running');
    if (p.recovery) row.classList.add('recovery');
    if (p.long_session) row.classList.add('long-session');
    if (p.running && idleSeconds >= idleThreshold) row.classList.add('idle-dim');

    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = p.name;
    row.appendChild(name);

    const counter = document.createElement('span');
    counter.className = 'counter';
    counter.textContent = fmtCounter(elapsedSecondsForProject(p));
    row.appendChild(counter);

    if (p.recovery) {
      // Recovery row: replace dot with two text buttons stacked below
      const placeholder = document.createElement('span');
      row.appendChild(placeholder);

      const actions = document.createElement('div');
      actions.className = 'recovery-actions';

      const stopBtn = document.createElement('button');
      stopBtn.className = 'text-btn';
      stopBtn.textContent = `Stop at ${new Date(p.proposed_stop_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}`;
      stopBtn.addEventListener('click', async () => {
        await pywebview.api.recovery_stop(p.name);
      });

      const resumeBtn = document.createElement('button');
      resumeBtn.className = 'text-btn';
      resumeBtn.textContent = 'Resume';
      resumeBtn.addEventListener('click', async () => {
        await pywebview.api.recovery_resume(p.name);
      });

      actions.appendChild(stopBtn);
      actions.appendChild(resumeBtn);
      row.appendChild(actions);
    } else {
      const dot = document.createElement('button');
      dot.className = 'dot ' + (p.running ? 'red' : 'green');
      if (p.running && idleSeconds >= idleThreshold) dot.classList.add('pulsing');
      dot.addEventListener('click', async () => {
        if (!p.running) {
          await pywebview.api.start_timer(p.name);
        } else {
          // Stop immediately. Open inline note for this row.
          await pywebview.api.stop_timer(p.name);
          openNoteFor = p.name;
          if (idleSeconds >= idleThreshold) {
            // Capture trim timestamp = now - idleSeconds
            pendingTrim[p.name] = new Date(Date.now() - idleSeconds * 1000).toISOString();
          }
          render();
          const inputEl = document.querySelector(`input[data-note-for="${p.name}"]`);
          if (inputEl) inputEl.focus();
        }
      });
      row.appendChild(dot);
    }

    rowsEl.appendChild(row);

    if (openNoteFor === p.name) {
      const wrap = document.createElement('div');
      wrap.className = 'row';
      wrap.style.borderTop = 'none';

      const noteWrap = document.createElement('div');
      noteWrap.className = 'note-input-wrap';

      const input = document.createElement('input');
      input.className = 'note-input';
      input.placeholder = 'what did you work on?';
      input.dataset.noteFor = p.name;

      input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
          await pywebview.api.attach_note(p.name, input.value, false);
          openNoteFor = null;
          delete pendingTrim[p.name];
          render();
        } else if (e.key === 'Escape') {
          await pywebview.api.attach_note(p.name, '', false);
          openNoteFor = null;
          delete pendingTrim[p.name];
          render();
        }
      });

      noteWrap.appendChild(input);

      if (pendingTrim[p.name]) {
        const trimTime = new Date(pendingTrim[p.name]).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        const keepBtn = document.createElement('button');
        keepBtn.className = 'text-btn';
        keepBtn.textContent = 'keep';
        keepBtn.addEventListener('click', async () => {
          await pywebview.api.attach_note(p.name, input.value, false);
          openNoteFor = null;
          delete pendingTrim[p.name];
          render();
        });
        const trimBtn = document.createElement('button');
        trimBtn.className = 'text-btn';
        trimBtn.textContent = `trim ${trimTime}`;
        trimBtn.addEventListener('click', async () => {
          await pywebview.api.attach_note(p.name, input.value, true);
          openNoteFor = null;
          delete pendingTrim[p.name];
          render();
        });
        noteWrap.appendChild(keepBtn);
        noteWrap.appendChild(trimBtn);
      }

      wrap.appendChild(noteWrap);
      rowsEl.appendChild(wrap);
    }
  }
}

// Called from Python via window.evaluate_js
window.setState = function (newState) {
  state = newState;
  render();
};

window.setIdle = function (seconds, thresholdSeconds) {
  idleSeconds = seconds;
  idleThreshold = thresholdSeconds;
  render();
};

// Settings panel
function wireSettings() {
  const panel = document.getElementById('settings-panel');
  const btn = document.getElementById('settings-btn');
  const closeBtn = document.getElementById('settings-close');
  const aot = document.getElementById('setting-always-on-top');
  const idle = document.getElementById('setting-idle-threshold');
  const rememberPos = document.getElementById('setting-remember-position');
  const resetPos = document.getElementById('setting-reset-position');

  btn.addEventListener('click', async () => {
    if (panel.hidden) {
      const s = await pywebview.api.get_settings();
      aot.checked = s.always_on_top;
      idle.value = s.idle_threshold_minutes;
      rememberPos.checked = s.remember_window_position;
    }
    panel.hidden = !panel.hidden;
  });

  closeBtn.addEventListener('click', () => { panel.hidden = true; });

  aot.addEventListener('change', () => pywebview.api.update_setting('always_on_top', aot.checked));
  idle.addEventListener('change', () => pywebview.api.update_setting('idle_threshold_minutes', parseInt(idle.value, 10) || 15));
  rememberPos.addEventListener('change', () => pywebview.api.update_setting('remember_window_position', rememberPos.checked));
  resetPos.addEventListener('click', () => pywebview.api.reset_window_position());

  document.getElementById('add-btn').addEventListener('click', () => {
    // No-op in v1; tooltip explains
  });
}

// 1s tick to update running counters from Date.now() (no Python roundtrip)
setInterval(() => {
  // Re-render counters only (cheap full re-render is fine here too)
  render();
}, 1000);

document.addEventListener('DOMContentLoaded', () => {
  wireSettings();
  // Request initial state
  if (window.pywebview && window.pywebview.api) {
    pywebview.api.get_state().then((s) => {
      state = s;
      render();
    });
    pywebview.api.get_settings().then((s) => {
      idleThreshold = (s.idle_threshold_minutes || 15) * 60;
      render();
    });
  }
});
```

- [ ] **Step 2: Commit**

```bash
git add ui/app.js
git commit -m "feat: UI rendering, button handlers, note input, settings wiring"
```

---

## Task 13: main.py — pywebview window + JS API + state watcher

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write `main.py`**

```python
"""WorkClock entry point: pywebview window + state watcher + JS API."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
import webview
from filelock import FileLock, Timeout
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from workclock import hours, idle, recovery, settings, state
from workclock.paths import normalize_path

UI_DIR = Path(__file__).parent / "ui"
INDEX = (UI_DIR / "window.html").as_uri()


def _now() -> datetime:
    return datetime.now().astimezone()


def _state_with_recovery_flags() -> dict:
    """Read state and decorate each project with recovery + long_session flags."""
    s = state.read_state()
    sf = state._state_file()
    state_mtime = (
        datetime.fromtimestamp(sf.stat().st_mtime, tz=timezone.utc)
        if sf.exists() else _now()
    )
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
    now = _now()

    rec_items = recovery.check_recovery(s, now=now, boot_time=boot_time, state_mtime=state_mtime)
    rec_by_name = {r.name: r for r in rec_items}

    for p in s["projects"]:
        if p["name"] in rec_by_name:
            r = rec_by_name[p["name"]]
            p["recovery"] = True
            p["proposed_stop_time"] = r.proposed_stop_time.isoformat()
        else:
            p["recovery"] = False
        p["long_session"] = recovery.is_long_session(p, now=now)
    return s


class API:
    """JS-callable methods. All return JSON-serializable data."""

    def __init__(self, window_ref):
        self._window_ref = window_ref
        self._pending_session = {}  # name -> {"started_at": iso, "stopped_at": iso, "trim_to_idle": bool}

    def get_state(self) -> dict:
        return _state_with_recovery_flags()

    def get_settings(self) -> dict:
        return settings.read_settings()

    def update_setting(self, key: str, value) -> dict:
        s = settings.read_settings()
        s[key] = value
        settings.write_settings(s)
        # Apply live where applicable
        if key == "always_on_top" and self._window_ref[0]:
            self._window_ref[0].on_top = bool(value)
        return s

    def reset_window_position(self) -> None:
        s = settings.read_settings()
        s["window_position"] = None
        settings.write_settings(s)
        if self._window_ref[0]:
            screen = webview.screens[0] if webview.screens else None
            x = (screen.width - 420) if screen else 1280
            y = 100
            self._window_ref[0].move(x, y)

    def add_project(self, raw_path: str, name: str | None = None) -> dict:
        """Add a project. Used by Claude indirectly (Claude usually edits state.json)."""
        win_path = normalize_path(raw_path)
        display_name = name or Path(raw_path.replace("\\", "/")).name
        upper_name = display_name.upper().replace(" ", "_")

        def mut(s):
            for p in s["projects"]:
                if p["name"] == upper_name:
                    return
            s["projects"].append({
                "name": upper_name,
                "path": win_path,
                "running": False,
                "started_at": None,
                "today_seconds": 0,
            })

        new_state = state.mutate_state(mut)

        # Ensure hours.md exists with header
        project_dir = Path(win_path)
        if project_dir.exists():
            hours_file = project_dir / "hours.md"
            if not hours_file.exists():
                hours_file.write_text(f"# Hours — {display_name}\n", encoding="utf-8")

        return new_state

    def remove_project(self, name: str) -> dict:
        def mut(s):
            s["projects"] = [p for p in s["projects"] if p["name"] != name]
        return state.mutate_state(mut)

    def start_timer(self, name: str) -> dict:
        now = _now()

        def mut(s):
            for p in s["projects"]:
                if p["name"] == name and not p["running"]:
                    p["running"] = True
                    p["started_at"] = now.isoformat()
        return state.mutate_state(mut)

    def stop_timer(self, name: str) -> dict:
        """Stop the timer. Pending session info is captured for attach_note."""
        now = _now()
        captured = {}

        def mut(s):
            for p in s["projects"]:
                if p["name"] == name and p["running"]:
                    started_iso = p["started_at"]
                    captured["started_at"] = started_iso
                    captured["stopped_at"] = now.isoformat()
                    captured["path"] = p["path"]
                    captured["display_name"] = Path(p["path"].replace("\\", "/")).name
                    started = datetime.fromisoformat(started_iso)
                    elapsed = max(0, int((now - started).total_seconds()))
                    p["today_seconds"] += elapsed
                    p["running"] = False
                    p["started_at"] = None

        new_state = state.mutate_state(mut)
        if captured:
            self._pending_session[name] = captured
        return new_state

    def attach_note(self, name: str, note: str, trim_to_idle: bool) -> None:
        """Finalize the most recent stop with an optional note and optional trim."""
        info = self._pending_session.pop(name, None)
        if not info:
            return
        start = datetime.fromisoformat(info["started_at"])
        stop = datetime.fromisoformat(info["stopped_at"])

        if trim_to_idle:
            idle_secs = idle.get_idle_seconds()
            trim_to = _now()
            from datetime import timedelta
            trim_to = trim_to - timedelta(seconds=idle_secs)
            if trim_to > start:
                # Adjust today_seconds: we already added (stop - start); now correct to (trim_to - start)
                old_elapsed = int((stop - start).total_seconds())
                new_elapsed = int((trim_to - start).total_seconds())
                delta = new_elapsed - old_elapsed  # negative

                def mut(s):
                    for p in s["projects"]:
                        if p["name"] == name:
                            p["today_seconds"] = max(0, p["today_seconds"] + delta)
                state.mutate_state(mut)
                stop = trim_to

        try:
            hours.append_session(
                Path(info["path"]),
                info["display_name"],
                start,
                stop,
                note.strip() if note and note.strip() else None,
            )
        except Exception as e:
            print(f"[WorkClock] failed to append hours.md: {e}", file=sys.stderr)

    def recovery_stop(self, name: str) -> dict:
        """Resolve a recovery row by stopping at proposed_stop_time."""
        now = _now()
        sf_mtime = (
            datetime.fromtimestamp(state._state_file().stat().st_mtime, tz=timezone.utc).astimezone()
            if state._state_file().exists() else now
        )
        boot = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc).astimezone()
        proposed = max(boot, sf_mtime)

        captured = {}

        def mut(s):
            for p in s["projects"]:
                if p["name"] == name and p["running"]:
                    started = datetime.fromisoformat(p["started_at"])
                    captured["started_at"] = p["started_at"]
                    captured["path"] = p["path"]
                    captured["display_name"] = Path(p["path"].replace("\\", "/")).name
                    elapsed = max(0, int((proposed - started).total_seconds()))
                    p["today_seconds"] += elapsed
                    p["running"] = False
                    p["started_at"] = None

        state.mutate_state(mut)
        if captured:
            try:
                hours.append_session(
                    Path(captured["path"]),
                    captured["display_name"],
                    datetime.fromisoformat(captured["started_at"]),
                    proposed,
                    note="(recovered)",
                )
            except Exception as e:
                print(f"[WorkClock] recovery append failed: {e}", file=sys.stderr)
        return _state_with_recovery_flags()

    def recovery_resume(self, name: str) -> dict:
        """Resolve a recovery row by leaving the timer running as-is.

        We just nudge state.mtime forward (no-op write) so subsequent recovery checks
        treat this timer as legitimate.
        """
        def mut(s):
            pass  # no-op write to refresh mtime
        state.mutate_state(mut)
        return _state_with_recovery_flags()


class StateChangeHandler(FileSystemEventHandler):
    def __init__(self, window_ref):
        self._window_ref = window_ref
        self._last_push = 0.0

    def on_modified(self, event):
        if Path(event.src_path).name != "state.json":
            return
        # Debounce
        now = time.time()
        if now - self._last_push < 0.2:
            return
        self._last_push = now
        try:
            s = _state_with_recovery_flags()
            if self._window_ref[0]:
                self._window_ref[0].evaluate_js(f"window.setState({json.dumps(s)})")
        except Exception as e:
            print(f"[WorkClock] state push failed: {e}", file=sys.stderr)


def _idle_loop(window_ref):
    while True:
        time.sleep(30)
        try:
            s = settings.read_settings()
            threshold_seconds = int(s.get("idle_threshold_minutes", 15)) * 60
            idle_secs = idle.get_idle_seconds()
            if window_ref[0]:
                window_ref[0].evaluate_js(
                    f"window.setIdle({idle_secs}, {threshold_seconds})"
                )
        except Exception:
            pass


def _save_position_loop(window_ref):
    while True:
        time.sleep(5)
        try:
            s = settings.read_settings()
            if not s.get("remember_window_position"):
                continue
            w = window_ref[0]
            if w is None:
                continue
            x, y = w.x, w.y
            current = s.get("window_position")
            if current != [x, y]:
                s["window_position"] = [x, y]
                settings.write_settings(s)
        except Exception:
            pass


def _enforce_single_instance() -> FileLock:
    state._state_dir().mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(state._state_dir() / "gui.lock"))
    try:
        lock.acquire(timeout=0.5)
    except Timeout:
        print("WorkClock is already running.", file=sys.stderr)
        sys.exit(0)
    return lock


def main():
    gui_lock = _enforce_single_instance()

    s = settings.read_settings()
    pos = s.get("window_position") or [1280, 100]

    window_ref = [None]
    api = API(window_ref)

    window = webview.create_window(
        "WorkClock",
        INDEX,
        js_api=api,
        width=420,
        height=400,
        x=pos[0],
        y=pos[1],
        on_top=bool(s.get("always_on_top", True)),
        frameless=True,
        resizable=False,
        background_color="#0a0a0a",
    )
    window_ref[0] = window

    # Watchdog observer on state.json
    handler = StateChangeHandler(window_ref)
    observer = Observer()
    observer.schedule(handler, str(state._state_dir()), recursive=False)
    observer.start()

    # Idle + position threads
    threading.Thread(target=_idle_loop, args=(window_ref,), daemon=True).start()
    threading.Thread(target=_save_position_loop, args=(window_ref,), daemon=True).start()

    try:
        webview.start()
    finally:
        observer.stop()
        observer.join(timeout=2)
        gui_lock.release()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-launch the app once to confirm it opens**

```bash
cd "$PROJECT"
./venv/Scripts/python.exe main.py
```

Expected: a small frameless amber-on-black window opens, top-right area, says "WORKCLOCK" at top, shows "No projects. Ask Claude to add one." in the body. Close the window to exit.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: pywebview window, JS API bridge, state watcher, idle/position threads"
```

---

## Task 14: WorkClock.bat launcher

**Files:**
- Create: `WorkClock.bat`

- [ ] **Step 1: Write `WorkClock.bat`**

```batch
@echo off
REM WorkClock launcher — runs the app windowless via pythonw

cd /d "%~dp0"

if not exist "venv\Scripts\pythonw.exe" (
  echo venv missing. Run setup first.
  pause
  exit /b 1
)

start "" "venv\Scripts\pythonw.exe" "main.py"
```

- [ ] **Step 2: Smoke-test by double-clicking `WorkClock.bat` in Windows Explorer**

(Or invoke from WSL: `cmd.exe /c "C:\Users\Xliminal\Code\PersonalProjects\WorkClock\WorkClock.bat"`.)

Expected: window appears within 1–2 seconds, no command prompt window remains visible.

- [ ] **Step 3: Commit**

```bash
git add WorkClock.bat
git commit -m "feat: WorkClock.bat launcher (windowless pythonw)"
```

---

## Task 15: README.md (full schema reference)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace placeholder README with full content**

```markdown
# WorkClock

A tiny always-on-top time tracker for working across multiple projects.

## How it works

A frameless amber-on-black window sits in the top-right of your screen with one row per project: project name, today's elapsed counter, and a colored dot. **Green** means idle; click it to start. **Red** means running; click it to stop, optionally typing a note when prompted. Sessions are appended to a `hours.md` file at the root of each project.

You manage projects (add, remove, start, stop) by talking to Claude in conversation — Claude edits the app's `state.json` file directly. The window watches that file and updates instantly. There is no CLI.

## Launching

Double-click `WorkClock.bat`, or run from WSL:

```bash
cmd.exe /c "C:\\Users\\Xliminal\\Code\\PersonalProjects\\WorkClock\\WorkClock.bat"
```

First-time setup (only once):

```bash
cd "C:\\Users\\Xliminal\\Code\\PersonalProjects\\WorkClock"
C:\\Users\\Xliminal\\AppData\\Local\\Programs\\Python\\Python313\\python.exe -m venv venv
venv\\Scripts\\python.exe -m pip install -r requirements.txt
```

Single-instance: re-launching when already running is a no-op.

## Where things live

| Thing | Location |
|---|---|
| App code | `C:\Users\Xliminal\Code\PersonalProjects\WorkClock\` |
| `state.json` (project list, running timers) | `%APPDATA%\WorkClock\state.json` |
| `settings.json` | `%APPDATA%\WorkClock\settings.json` |
| State lock file | `%APPDATA%\WorkClock\state.lock` |
| Single-instance lock | `%APPDATA%\WorkClock\gui.lock` |
| Per-project session log | `<project_root>\hours.md` |

From WSL, `%APPDATA%` = `/mnt/c/Users/Xliminal/AppData/Roaming/`.

## `state.json` schema (Claude's contract)

This is the file Claude edits directly to add/remove projects and start/stop timers. The schema must be honored exactly.

```json
{
  "today": "2026-04-29",
  "projects": [
    {
      "name": "GLORIA",
      "path": "C:\\Users\\Xliminal\\Code\\PersonalProjects\\Gloria",
      "running": false,
      "started_at": null,
      "today_seconds": 0
    },
    {
      "name": "WTF_IS_PHYSICS",
      "path": "\\\\wsl$\\Ubuntu\\home\\jermsai\\Code\\WTF_Is_Physics",
      "running": true,
      "started_at": "2026-04-29T13:42:11-05:00",
      "today_seconds": 4980
    }
  ]
}
```

**Fields:**

- `today` — local date (`YYYY-MM-DD`) the `today_seconds` totals correspond to. On read, if this differs from the system date, all `today_seconds` reset to 0 and `today` advances to the system date.
- `projects[].name` — UPPERCASE display + lookup key. Generated from folder basename.
- `projects[].path` — Windows-readable path. Either `C:\...` (Windows-side) or `\\wsl$\Ubuntu\...` (Linux-side).
- `projects[].running` — boolean.
- `projects[].started_at` — ISO 8601 with timezone offset (e.g. `2026-04-29T13:42:11-05:00`) when running. `null` otherwise.
- `projects[].today_seconds` — integer seconds accumulated for `today`, *not counting* the current session if running.

### How Claude mutates `state.json`

1. Read `state.json`.
2. Modify the JSON in place (add/remove a project, toggle `running`, set/clear `started_at`).
3. Write atomically: write to `state.json.tmp`, then rename to `state.json` (the `Edit` tool's atomic write semantics are sufficient — it does not need to take the filelock).
4. The GUI watcher detects the change within ~200ms and re-renders.

**Adding a project:**
- Append a new `projects[]` entry. Set `running: false`, `started_at: null`, `today_seconds: 0`.
- Convert any `/home/jermsai/...` path to `\\wsl$\Ubuntu\home\jermsai\...`. Convert any `/mnt/c/...` path to `C:\...`.
- After saving state.json, also create `hours.md` at the project root (with header `# Hours — <DisplayName>`) if it doesn't exist.

**Starting a timer:**
- Set `running: true`, `started_at` = current ISO timestamp with timezone.

**Stopping a timer (and logging to hours.md):**
1. Compute `elapsed_seconds = now - started_at`.
2. Add `elapsed_seconds` to `today_seconds`.
3. Set `running: false`, `started_at: null`.
4. Append the session bullet to `<path>/hours.md` (see "hours.md format" below).

## `hours.md` format

```markdown
# Hours — Gloria

## 2026-04-29
- 09:15–11:43 (2h 28m) — auth refactor
- 13:30–15:00 (1h 30m)

## 2026-04-28
- 10:00–12:15 (2h 15m) — initial build
```

**Rules:**

- Header line: `# Hours — <DisplayName>` (folder basename, normal case).
- Day sections: `## YYYY-MM-DD`, sorted **descending** (newest day on top).
- Bullets within a day: sorted **ascending** by start time.
- Time format: 24-hour local, `HH:MM`.
- En-dash between start and stop: `09:15–11:43`.
- Duration: `Xh Ym` if total ≥ 60 minutes, else `Ym` (e.g. `45m`, `2h 5m`). Seconds are truncated, not rounded.
- Note (optional): separated from duration by ` — ` (em-dash with spaces).
- **Sessions crossing midnight** are filed under the *start* date.

### Duration math

```
elapsed_seconds = (stop - start).total_seconds()
total_minutes = elapsed_seconds // 60
hours = total_minutes // 60
minutes = total_minutes % 60
result = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
```

## `settings.json`

```json
{
  "always_on_top": true,
  "idle_threshold_minutes": 15,
  "remember_window_position": true,
  "window_position": [1280, 100]
}
```

Edit via the gear icon in the window. Missing keys merge with defaults on read.

## Recovery behavior

**Crash recovery:** if `state.json` says a timer is `running` with a `started_at` that predates the system boot or the `state.json` modification time, the GUI shows that row in a recovery state with two buttons:

- **Stop at \<time\>** — uses `max(boot_time, state.json mtime)` as the stop time, appends to `hours.md` with the note `(recovered)`, and clears the running state.
- **Resume** — leaves the timer running with the original `started_at`.

**Long-session warning:** if a timer has been running 12+ hours, the row gets a yellow left border. No prompt, no auto-action.

## Tests

```bash
cd "C:\\Users\\Xliminal\\Code\\PersonalProjects\\WorkClock"
venv\\Scripts\\python.exe -m pytest tests/ -v
```

Or from WSL:

```bash
/mnt/c/Users/Xliminal/Code/PersonalProjects/WorkClock/venv/Scripts/python.exe -m pytest tests/ -v
```

## Out of scope (v1)

- Reporting, summing, or analytics commands. Ask Claude to summarize.
- Git-commit or calendar reconciliation. Done ad-hoc by asking Claude.
- Notifications (toast/sound).
- Pomodoro / forced breaks.
- Mobile, web, cross-platform.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: full README with schema reference and Claude mutation contract"
```

---

## Task 16: Final verification — full test suite + manual smoke test

- [ ] **Step 1: Run the full test suite**

```bash
cd "$PROJECT"
./venv/Scripts/python.exe -m pytest tests/ -v
```

Expected: all tests pass (paths: 8, hours: 14, state: 5, recovery: 6, settings: 3 = **36 passed**).

- [ ] **Step 2: Manual smoke test — launch and basic flow**

Launch:

```bash
cmd.exe /c "$PROJECT/WorkClock.bat"
```

Verify:
- Window appears, frameless, amber-on-black, top-right area.
- Body says "No projects. Ask Claude to add one."
- Window stays on top of other apps (try clicking a browser; WorkClock should remain visible).

- [ ] **Step 3: Manual smoke test — add a test project via state.json edit**

While the app is running, create a temporary project folder:

```bash
mkdir -p /tmp/SmokeTestProj
```

Edit `/mnt/c/Users/Xliminal/AppData/Roaming/WorkClock/state.json` to add:

```json
{
  "today": "<today's date>",
  "projects": [
    {
      "name": "SMOKETESTPROJ",
      "path": "\\\\wsl$\\Ubuntu\\tmp\\SmokeTestProj",
      "running": false,
      "started_at": null,
      "today_seconds": 0
    }
  ]
}
```

Verify within ~1 second:
- A new row labeled `SMOKETESTPROJ` appears.
- Counter shows `00:00:00`.
- A green dot is on the right.

- [ ] **Step 4: Manual smoke test — start timer**

Click the green dot.

Verify:
- Dot turns red.
- Counter starts ticking each second (`00:00:01`, `00:00:02`, ...).

Wait ~30 seconds.

- [ ] **Step 5: Manual smoke test — stop timer with note**

Click the red dot.

Verify:
- Dot turns green immediately.
- Counter stops at the elapsed value (e.g., `00:00:32`).
- An inline text input appears below the row: "what did you work on?".

Type `smoke test session` and press Enter.

Verify:
- Input collapses.
- File `/tmp/SmokeTestProj/hours.md` exists with content like:

```markdown
# Hours — SmokeTestProj

## <today>
- HH:MM–HH:MM (0m) — smoke test session
```

- [ ] **Step 6: Manual smoke test — settings panel**

Click the gear icon (top-right of window).

Verify:
- Panel slides down with: always-on-top checkbox, idle threshold input, remember-position checkbox, reset-position button, close button.
- Toggle "always on top" off; verify the WorkClock window can be hidden behind another window.
- Toggle it back on.
- Click Close.

- [ ] **Step 7: Manual smoke test — restart persistence**

Close the WorkClock window. Re-launch via `WorkClock.bat`.

Verify:
- The `SMOKETESTPROJ` row reappears in the same position.
- `today_seconds` reflects the smoke-test session (counter shows ~`00:00:32`).
- Window opens at the last position.

- [ ] **Step 8: Cleanup smoke test artifacts**

Edit `state.json` to remove the `SMOKETESTPROJ` entry (set `projects: []`).

```bash
rm -rf /tmp/SmokeTestProj
```

- [ ] **Step 9: Commit any final fixes if smoke test surfaced bugs**

If any step required code changes, commit them with descriptive messages. If everything worked first time, no commit needed.

- [ ] **Step 10: Final commit — mark v1 complete**

```bash
git log --oneline
```

Expected: ~15 commits forming the build history. Optionally tag:

```bash
git tag v1.0.0 -m "WorkClock v1: timing only"
```

---

## Self-review checklist (already performed)

**Spec coverage:**
- ✅ Always-on-top window with project rows, green/red dot — Tasks 10, 11, 12, 13.
- ✅ Multiple simultaneous timers — state.json supports independent `running` per project; no mutual exclusion logic.
- ✅ Per-project `hours.md` with daily-section format — Task 5.
- ✅ Skippable inline note on stop — Task 12.
- ✅ Claude controls via `state.json` edits — documented in README (Task 15).
- ✅ Idle nudge (visual only) — Tasks 9, 12, 13.
- ✅ Crash + 12-hour recovery — Tasks 7, 13.
- ✅ Settings panel with always-on-top, idle threshold, position — Tasks 8, 10, 11, 12, 13.
- ✅ Path normalization (Linux/WSL/Windows) — Task 3.
- ✅ Atomic writes + filelock — Task 6.
- ✅ Single-instance enforcement — Task 13 (`_enforce_single_instance`).
- ✅ Sessions crossing midnight filed under start date — Task 5 test.
- ✅ README serves as Claude's reference doc — Task 15.

**Type/name consistency:**
- `normalize_path(input_path: str) -> str` — used everywhere as `normalize_path(...)`.
- `format_duration(seconds: int) -> str` and `format_time(dt: datetime) -> str` — consistent.
- `append_session(project_dir, display_name, start, stop, note)` — same signature in tests, in `main.py` callers.
- `read_state()` / `mutate_state(fn)` / `_write_state_unsafe(state)` — consistent.
- `read_settings()` / `write_settings(settings)` — consistent.
- `check_recovery(state, now, boot_time, state_mtime)` and `is_long_session(project, now, threshold_hours=12)` — consistent.
- JS API methods on `API` class match `pywebview.api.<name>` calls in `app.js`: `get_state`, `get_settings`, `update_setting`, `reset_window_position`, `add_project`, `remove_project`, `start_timer`, `stop_timer`, `attach_note`, `recovery_stop`, `recovery_resume`. ✅

**Placeholder scan:** No TBDs, no "implement later", no "similar to Task N", no missing code blocks. All tests have full assertions; all implementations have full bodies.
