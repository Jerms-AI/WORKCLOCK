# WorkClock — Design

A tiny always-on-top time tracker for working across multiple projects, with a digital-readout aesthetic. The user clicks a colored dot to start/stop a per-project timer; sessions are appended to a `hours.md` file at each project's root. Claude (the assistant) controls the same state by directly editing the app's state file in conversation, so the user can manage projects and toggle timers via natural language without a CLI.

## Goals & non-goals

**Goals (v1):**
- Always-on-top window with one row per project: name, today's elapsed counter, start/stop dot.
- Multiple timers may run simultaneously (no auto-stop on switch).
- Each session is appended to a `hours.md` file at the project root, in a daily-section markdown format with optional skippable note.
- Claude can add/remove projects and start/stop timers by editing the app's `state.json` directly — no CLI surface.
- Gentle idle nudge after configurable threshold (no auto-action).
- Crash and long-session recovery on launch.

**Non-goals (v1):**
- Reporting, summing, or analytics commands.
- Git-commit or calendar reconciliation. (User reconciles ad-hoc by asking Claude.)
- Notifications (toast or sound).
- Pomodoro / forced breaks.
- Mobile, web, or cross-platform support. Windows desktop only.

## Architecture

**Tech stack:** Python 3.13 (already installed at `C:\Users\Xliminal\AppData\Local\Programs\Python\Python313\`) + `pywebview` for the always-on-top window. UI is HTML/CSS/JS rendered in the system webview (no Chromium download).

**Process model:** single GUI process. No background daemon, no CLI tool. The app is the only thing that runs.

**Control surfaces (both mutate the same `state.json`):**
1. **GUI buttons** — user clicks dots in the window.
2. **Claude editing files directly** — Claude uses standard file-edit tools to modify `state.json` and `hours.md` based on user requests in conversation. The GUI watches `state.json` and re-renders when it changes.

**Concurrency model:** `state.json` is the single source of truth. Mutators (GUI button handlers, or Claude's edits) take a `filelock` on `state.lock` for read-modify-write. Display reads (the GUI's polling loop) skip the lock to keep the UI snappy. Writes are atomic: write to `state.json.tmp`, fsync, rename.

**File watching:** the GUI uses `watchdog` to observe `state.json` and re-render rows when the file changes (covers Claude's edits arriving from outside the GUI).

## Visual & UX

### Window

- Frameless or thin chrome, draggable from anywhere on the window.
- Compact fixed width (~420px). Height grows with the number of project rows.
- Default: always on top, position remembered between launches.
- Aesthetic: digital readout. Background `#0a0a0a`, primary text `#ffb347` (amber), monospace font (`JetBrains Mono` or `IBM Plex Mono`, fall back to system monospace).

### Per-row anatomy (left → right)

1. **Project name** — uppercase, e.g. `GLORIA`, `WTF_IS_PHYSICS`.
2. **Today's elapsed counter** — `HH:MM:SS`. When idle, shows today's accumulated time so far. When running, ticks live every second. Resets to `00:00:00` at local midnight.
3. **Indicator dot / button** — round, ~28px. Green when idle. Red when running. Click to toggle.

### Stop interaction

Clicking a red dot:
1. Stops the timer immediately (the dot turns green; nothing waits on user input).
2. Reveals an inline single-line text field on the row: placeholder "what did you work on?".
3. **Save with note:** press Enter.
4. **Save without note:** press Esc, click outside the field, or click any other row's dot.
5. Either way, the session is appended to `hours.md` and the field collapses.

### Idle nudge (visual only)

While any timer is running, the app polls Windows idle time (`GetLastInputInfo` via ctypes) every 30 seconds. When idle exceeds the threshold (default 15 min):
- The running row's counter dims to ~40% opacity.
- The red dot pulses (slow fade ~2s cycle).
- Activity resumes → dim/pulse clears immediately. No auto-stop.

When the user clicks the dot to stop after a long idle, the inline row reveals two compact buttons next to the note field: `[keep]` and `[trim 14:32]` (the timestamp is the moment input last occurred). Clicking `[trim]` records the stop time as that timestamp instead of now. Clicking `[keep]` (or just typing a note and pressing Enter) logs the full session ending now.

### Settings

A small gear icon at the top of the window opens a settings panel:
- **Always on top** — toggle (default ON).
- **Idle nudge threshold** — minutes input (default 15).
- **Window position** — "remember" toggle (default ON), "reset to top-right" button.

Settings are persisted to `settings.json` (see Data files below).

### Top-bar UI

- Gear icon (settings).
- `+` icon — visual placeholder only in v1. Hovering shows the tooltip `Ask Claude to add a project`. Click is a no-op.

## Data files

### `state.json` (the source of truth)

Location: `%APPDATA%\WorkClock\state.json` (accessible from WSL at `/mnt/c/Users/Xliminal/AppData/Roaming/WorkClock/state.json`).

```json
{
  "today": "2026-04-29",
  "projects": [
    {
      "name": "GLORIA",
      "path": "C:\\Users\\Xliminal\\Code\\PersonalProjects\\Gloria",
      "running": false,
      "started_at": null,
      "today_seconds": 8100
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

**Field semantics:**
- `today` — the local date the `today_seconds` totals correspond to. On any read, if this differs from the system's current local date, all `today_seconds` reset to 0 and `today` updates to the current date.
- `projects[].name` — uppercase. Used as the display label and as the unique key in conversation ("start the GLORIA timer"). Generated from the folder basename when added.
- `projects[].path` — Windows-readable path. Either `C:\...` for Windows-side projects, or `\\wsl$\Ubuntu\...` for Linux-side projects.
- `projects[].running` — boolean.
- `projects[].started_at` — ISO 8601 with timezone offset, set when running. `null` when not running.
- `projects[].today_seconds` — accumulated seconds for today *not counting* the current session if running. When the user clicks stop, the elapsed session seconds get added to this field and `running` flips to false.

**Atomic write:** mutators write `state.json.tmp`, call fsync, then rename to `state.json`. Cross-process locking via `state.lock` using the `filelock` library.

### `settings.json`

Location: `%APPDATA%\WorkClock\settings.json`.

```json
{
  "always_on_top": true,
  "idle_threshold_minutes": 15,
  "remember_window_position": true,
  "window_position": [1280, 100]
}
```

### `state.lock`, `gui.lock`

Location: `%APPDATA%\WorkClock\`. Used by `filelock` for state mutations and single-instance GUI enforcement, respectively. Auto-cleaned by the library.

### `hours.md` (per project)

Location: `<project_root>/hours.md`. Created on first add of the project if absent.

**Format:**

```markdown
# Hours — Gloria

## 2026-04-29
- 09:15–11:43 (2h 28m) — auth refactor
- 13:30–15:00 (1h 30m)

## 2026-04-28
- 10:00–12:15 (2h 15m) — initial build
```

**Rules:**
- Header: `# Hours — <DisplayName>`. The display name is the folder basename in normal case (not uppercase). E.g., a project at `Code\PersonalProjects\Gloria` gets `# Hours — Gloria`. Stored project name (in state.json) is `GLORIA`.
- Day sections sorted descending (newest day at the top).
- Bullets within a day sorted ascending by start time.
- Times in 24-hour local time (`HH:MM`).
- Duration formatted as `Xh Ym` if total ≥ 60 min, else `Ym` (e.g. `45m`, `2h 5m`, `0h 5m` is invalid — collapse to `5m`).
- Note, when present, separated from duration by ` — ` (em-dash with spaces).
- En-dash between start and stop times (`09:15–11:43`).
- When stopping, the bullet is appended to today's section; if today's section doesn't exist, prepend a new `## YYYY-MM-DD` section at the top of the file (under the `# Hours — ...` header).
- **Sessions that cross midnight:** the bullet is filed under the *start* date's section, with the literal stop time shown (e.g. `23:30–00:45 (1h 15m)` under `## 2026-04-28`). Today-counter behavior: the seconds before midnight count toward yesterday's total (already past); seconds after midnight count toward today's `today_seconds`. This is handled by the date-rollover logic on next state read.

### Path normalization

Implemented in `workclock/paths.py`. Accepts paths in any of three forms and normalizes to the Windows-readable form for storage in `state.json`:

| Input | Stored as |
|---|---|
| `C:\foo\bar` | `C:\foo\bar` |
| `/mnt/c/foo/bar` | `C:\foo\bar` |
| `/home/jermsai/Code/X` | `\\wsl$\Ubuntu\home\jermsai\Code\X` |

Linux-side normalization assumes the WSL distro is `Ubuntu` (current setup). If the user ever has multiple distros, this becomes configurable. Out of scope for v1.

## Crash recovery & long-session safety

### Crash recovery

On every launch, the app inspects each project's `running: true` entries:
- Compares `started_at` to: (a) system boot time via `psutil.boot_time()`, (b) last write time of `state.json`.
- If `started_at` predates either signal, the row enters a recovery state on the first render.

**Recovery row UI:**
- Amber background tint.
- Counter shows the original `started_at` time, frozen.
- Two buttons replace the green/red dot:
  - **Stop at last activity** — uses `max(boot_time, state.json mtime)` as the stop time, appends to `hours.md`, clears running state, resumes normal row rendering. Shows the proposed stop time as editable text the user can override before confirming.
  - **Resume** — keeps `started_at` as-is, resumes counting. Used when the GUI just crashed but the user was actually working through it.

Each recovery row is handled independently. Other rows behave normally.

### 12-hour safety check

On every state read, if a running timer's `started_at` is more than 12 hours ago:
- The row gets a yellow border and a tooltip: `Running 12h+ — likely forgot to stop`.
- No prompt, no auto-action. Visible warning only.

This catches the "I went to bed without stopping" case on the next morning's glance.

## Repository layout

```
WorkClock/
├── README.md
├── WorkClock.bat                # double-click launcher → pythonw main.py
├── main.py                      # entry point: window + state watcher
├── requirements.txt             # pywebview, watchdog, filelock, psutil, pytest
├── workclock/
│   ├── __init__.py
│   ├── state.py                 # state.json read/write, atomic + filelock
│   ├── paths.py                 # path normalization
│   ├── hours.py                 # append to hours.md, format durations
│   ├── idle.py                  # GetLastInputInfo wrapper
│   └── recovery.py              # crash & long-session checks
├── ui/
│   ├── window.html              # one-page GUI shell
│   ├── style.css                # amber-on-black digital readout
│   └── app.js                   # row rendering, button handlers, polls state every 1s
├── tests/
│   ├── test_state.py
│   ├── test_hours.py
│   ├── test_paths.py
│   └── test_recovery.py
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-29-workclock-design.md   ← this file
```

App data is **not** in the repo. Lives in `%APPDATA%\WorkClock\`:
- `state.json`
- `settings.json`
- `state.lock`
- `gui.lock`

## README contents

The `README.md` at the repo root must include:

1. **What it is** — one line.
2. **How it works** — one paragraph: GUI buttons toggle timers; Claude mutates `state.json` directly; `hours.md` lives in each project root.
3. **Launching** — double-click `WorkClock.bat`, or for first-time setup: install Python deps with `pip install -r requirements.txt`.
4. **`state.json` schema** — the full JSON shape with field meanings. Critical reference for Claude across sessions.
5. **`hours.md` format** — exact bullet format, day-section conventions, append rules.
6. **Duration math reference** — how to compute `Xh Ym` from start/stop ISO timestamps.
7. **Settings** — file location, valid keys, defaults.
8. **Where things live** — `state.json`, `settings.json`, locks, project paths.
9. **Recovery behavior** — what happens after a crash, what the user sees.
10. **Out of scope (v1)** — reporting, git/calendar reconciliation, notifications, Pomodoro.

The README is also Claude's reference doc for the data contract — Claude re-reads it any session it needs to mutate state.

## Testing

`pytest` suite covers all file-mutation logic:

- `test_state.py` — atomic writes, lock acquisition, today rollover, schema validation.
- `test_hours.py` — append to existing day section, create new day section, duration formatting (`5m`, `1h 0m`, `2h 28m`), note formatting with em-dash, file-creation header.
- `test_paths.py` — Windows, `/mnt/c/`, `/home/jermsai/` → all three normalize correctly.
- `test_recovery.py` — `started_at` predates boot or state.json mtime → recovery state triggers; otherwise not.

GUI rendering itself is not unit-tested in v1 — manual smoke test on launch covers the row display, button states, idle pulse, and settings panel.

Tests run via `pytest` from the repo root. Can be invoked from WSL via `cmd.exe /c "C:\Users\Xliminal\AppData\Local\Programs\Python\Python313\python.exe -m pytest"`.

## Dependencies

Listed in `requirements.txt`:

- `pywebview` — system webview wrapper for the always-on-top window.
- `watchdog` — file-system event observer for `state.json`.
- `filelock` — cross-process locking for state mutations.
- `psutil` — boot time for crash recovery.
- `pytest` — test runner (dev dependency).

`tkinter` is unused (we're going pywebview), but ships with Python anyway. No additional Windows components needed beyond the system webview (Edge WebView2 on modern Windows, already present).

## Open questions deferred to implementation

- Exact pywebview window flags for "always on top" + "frameless" + "draggable from anywhere" — confirm during implementation. Fallback: thin chrome with custom title bar if frameless drag-anywhere is fragile.
- Exact font fallback chain — try `JetBrains Mono`, then `IBM Plex Mono`, then `Cascadia Mono`, then generic `monospace`.
- Whether to use HTML5 `<input>` for the inline note or a custom contenteditable. Default to `<input>` unless styling forces otherwise.
