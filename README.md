# WorkClock

A tiny always-on-top time tracker for working across multiple projects.

## How it works

A frameless amber-on-black window stays on top of everything. Each row shows a project's name, today's accumulated time, lifetime total, the current session counter, a start/stop dot, and a pause icon.

- **Green dot** → click to start a session.
- **Red dot** → click to stop. A modal appears asking for a note; you must type one and click Save (Enter also works).
- **Pause icon (⏸)** → green when a session is running. Click to pause: the project name, counter, and stop dot turn grey, and the pause icon turns yellow (▶). Click the yellow icon to resume.

Stopping a session writes one entry to a central `Time_Worked.json`, resets the per-row counter to `0:00`, and bumps `today` and `total` for that project.

You manage projects (add, remove, start, stop) by talking to Claude in conversation — Claude edits the app's `state.json` file directly. The window watches that file and updates within ~1s. There is no CLI, no settings UI.

## Launching

Double-click `WorkClock.bat`, or run from WSL:

```bash
cmd.exe /c "C:\\Users\\Xliminal\\Code\\PersonalProjects\\WorkClock\\WorkClock.bat"
```

To close the app: **Alt+F4** while the window is focused, or right-click its taskbar entry → Close.

First-time setup (only once):

```bash
cd "C:\\Users\\Xliminal\\Code\\PersonalProjects\\WorkClock"
C:\\Users\\Xliminal\\AppData\\Local\\Programs\\Python\\Python313\\python.exe -m venv venv
venv\\Scripts\\python.exe -m pip install -r requirements.txt
```

Single-instance: re-launching when already running is a no-op.

## Hardcoded defaults (no settings UI)

- Always on top: **on**
- Idle threshold (visual nudge): **15 min**
- Window starts at **(1280, 100)** — drag it anywhere; position is not remembered between launches.

If you want any of these adjustable from the UI, ask and I'll add a settings panel back.

## Where things live

| Thing | Location |
|---|---|
| App code | `C:\Users\Xliminal\Code\PersonalProjects\WorkClock\` |
| `state.json` (project list, running timers) | `%APPDATA%\WorkClock\state.json` |
| `Time_Worked.json` (central session log) | `%APPDATA%\WorkClock\Time_Worked.json` |
| State lock file | `%APPDATA%\WorkClock\state.lock` |
| Single-instance lock | `%APPDATA%\WorkClock\gui.lock` |
| Debug log | `%APPDATA%\WorkClock\debug.log` |
| Window screenshot tool | `tools/capture.py` (used by Claude to self-verify UI state) |

From WSL, `%APPDATA%` = `/mnt/c/Users/Xliminal/AppData/Roaming/`.

**Privacy note:** nothing about WorkClock is written into the project directories. The session log lives entirely in `%APPDATA%\WorkClock\Time_Worked.json` so accidental client transfers, git pushes, or zip exports of a project folder never leak time data.

## Display rules

- The big counter on each row is **the current session only**, formatted as `H:MM`. It rounds **down to the nearest 5 minutes** for display (so the first 5 real minutes show `0:00`). Internally seconds are tracked precisely.
- Below the project name: `today H.MM · total H.MM` — also rounded down to 5-min increments. Period is the separator (e.g. `today 2.15` means 2 hours 15 minutes).
- `today` resets at local midnight. `total` accumulates forever.
- When a row is **paused**, name + counter + stop dot all render in dim amber. Stop is disabled. Only the yellow pause icon is interactive.

## `state.json` schema (Claude's contract)

This is the file Claude edits to add/remove projects and toggle timer state. Honor the schema exactly — the GUI watches the file and re-renders on change.

```json
{
  "today": "2026-04-29",
  "projects": [
    {
      "name": "ASANDRA_POC",
      "path": "\\\\wsl$\\Ubuntu\\home\\jermsai\\Clients\\AMD\\Asandra_POC",
      "running": false,
      "paused": false,
      "started_at": null,
      "session_seconds": 0,
      "today_seconds": 0,
      "total_seconds": 0
    },
    {
      "name": "GLORIA",
      "path": "\\\\wsl$\\Ubuntu\\home\\jermsai\\Clients\\Gloria",
      "running": true,
      "paused": false,
      "started_at": "2026-04-29T13:42:11-05:00",
      "session_seconds": 0,
      "today_seconds": 4980,
      "total_seconds": 117300
    }
  ]
}
```

**Top level:**
- `today` — local date (`YYYY-MM-DD`) the `today_seconds` totals correspond to. On read, if this differs from the system date, all `today_seconds` reset to 0 and `today` advances.

**Per project:**
- `name` — UPPERCASE display + lookup key. Generated from folder basename.
- `path` — Windows-readable path. Either `C:\...` (Windows-side) or `\\wsl$\Ubuntu\...` (Linux-side via WSL).
- `running` — true when the timer is actively counting.
- `paused` — true when the session is paused (frozen, but considered in-progress).
- `started_at` — ISO 8601 with timezone (e.g. `2026-04-29T13:42:11-05:00`) when running. `null` otherwise (idle or paused).
- `session_seconds` — accumulated seconds of the *current* session that aren't currently being counted (i.e., everything before the most recent resume; 0 for a fresh start).
- `today_seconds` — committed seconds for `today`, *not* counting the in-progress session. Bumped on stop.
- `total_seconds` — lifetime committed seconds, *not* counting the in-progress session. Bumped on stop.

### State invariants

| State | running | paused | started_at | session_seconds |
|---|---|---|---|---|
| idle | false | false | null | 0 |
| running | true | false | ISO timestamp | accumulated from prior pauses (0 if first) |
| paused | false | true | null | total elapsed before pause |

The current displayed counter is computed as: `session_seconds + (now − started_at if running else 0)`. Stop sums that into `today_seconds` and `total_seconds`, then resets `session_seconds` and clears `started_at`.

### How Claude mutates `state.json`

1. Read `state.json`.
2. Modify the JSON in place.
3. Write atomically (the `Edit` tool's atomic write semantics are sufficient).
4. The GUI watcher detects the change within ~200ms and re-renders.

**Adding a project:**
- Append a new `projects[]` entry. Use the defaults from the schema above (all booleans false, all counters 0).
- Convert `/home/jermsai/...` → `\\wsl$\Ubuntu\home\jermsai\...`. Convert `/mnt/c/...` → `C:\...`.
- No file is created in the project's own directory.

**Starting a timer (idle → running):**
- Set `running: true`, `paused: false`, `started_at` = now, `session_seconds: 0`.

**Pausing (running → paused):** *(prefer using the GUI button — but documented for completeness)*
- Compute `delta = now - started_at`. Add to `session_seconds`.
- Set `running: false`, `paused: true`, `started_at: null`.

**Resuming (paused → running):**
- Set `running: true`, `paused: false`, `started_at` = now. Leave `session_seconds` intact.

**Stopping (any active state → idle, with note):**
- Compute `elapsed = session_seconds + (now - started_at if running else 0)`.
- Add `elapsed` to `today_seconds` and `total_seconds`.
- Reset `running: false`, `paused: false`, `started_at: null`, `session_seconds: 0`.
- Append a new entry to `Time_Worked.json` (see format below).

## `Time_Worked.json` format

A single JSON array at `%APPDATA%\WorkClock\Time_Worked.json`. One object per stopped session, oldest first.

```json
[
  {
    "project": "ASANDRA_POC",
    "date": "2026-04-29",
    "start": "2026-04-29T11:33:03.656971-04:00",
    "stop": "2026-04-29T11:33:06.475252-04:00",
    "duration_seconds": 2,
    "note": "stuff 1"
  }
]
```

**Fields:**
- `project` — the UPPERCASE name from `state.json`.
- `date` — local date of the session START (`YYYY-MM-DD`). Sessions crossing midnight are filed under the start date.
- `start`, `stop` — ISO 8601 with timezone offset.
- `duration_seconds` — integer; precise (not 5-min-rounded). Equals `stop - start` minus any paused intervals (since pauses don't accumulate while frozen).
- `note` — string the user typed, or `null` if blank/skipped.

**Append rules:**
- File is created (as `[]`) on app startup if missing.
- Append, never insert or sort. Order is chronological by stop time.
- Atomic write: write `Time_Worked.json.tmp`, then rename.

## Recovery behavior

There is no automatic crash recovery in v1. If the GUI dies mid-session (force-killed, PC restart), the in-memory session is lost: `today_seconds` and `total_seconds` are *not* updated, and no `Time_Worked.json` entry is written. On next launch, the project shows whatever last-committed values were on disk.

If you discover a missing session after the fact, ask Claude to append an entry to `Time_Worked.json` manually.

## Drag

The window is fully draggable from anywhere on the body that isn't a button or input. Implemented via Win32 `SetWindowPos` polling on a background Python thread, since pywebview's CSS-based drag and `easy_drag` don't work reliably with the WebView2 backend.

## Tests

```bash
cd "C:\\Users\\Xliminal\\Code\\PersonalProjects\\WorkClock"
venv\\Scripts\\python.exe -m pytest tests/ -v
```

Or from WSL:

```bash
/mnt/c/Users/Xliminal/Code/PersonalProjects/WorkClock/venv/Scripts/python.exe -m pytest tests/ -v
```

Coverage: path normalization, state read/mutate/atomic-write/today-rollover/legacy-backfill, `Time_Worked.json` append. UI behavior is verified manually + via Claude's screenshot tool (`tools/capture.py`).

## Build history & key decisions

The original spec is at `docs/superpowers/specs/2026-04-29-workclock-design.md` and the original plan is at `docs/superpowers/plans/2026-04-29-workclock-implementation.md`. **Both are partially obsolete** — the README above is the source of truth. Significant pivots from the original spec:

| Change | Why |
|---|---|
| Removed settings UI (gear, panel) | User wanted simplification. Always-on-top + 15-min idle are hardcoded. |
| Removed crash recovery + 12-hour warning | Adds complexity, low payoff. Lost sessions are accepted. |
| Renamed `hours.md` → `Time_Worked.json` | Switched to structured JSON for easier programmatic sums. |
| Moved log from project root → `%APPDATA%\WorkClock\` | Privacy: prevents accidental client transfer / git push leakage. |
| Added pause/resume button | Real workflow — phone calls, lunch — without ending the session. |
| Display rounded down to 5-min increments, no seconds | UI clarity. Internal tracking is still per-second. |
| Stop resets per-row counter to `0:00` | Counter = *current session* only. `today` / `total` shown separately. |
| Note input is a required modal overlay (no Esc skip) | Forces context-capture for every session. |
| Drag implemented via Win32 cursor-polling thread | pywebview's `easy_drag` and CSS `-webkit-app-region: drag` don't work in the WebView2 backend. |
| Always-on-top via Win32 `SetWindowPos` | pywebview's `Window.on_top` property only takes effect at creation, not runtime toggle. |
| Watchdog handles `on_created` + `on_moved` (not just `on_modified`) | Atomic writes (`.tmp` + rename) generate created/moved events, not modified. JS also polls every 3s as a safety net. |

## Common gotchas (for Claude in a fresh session)

- **WebView2 aggressively caches HTML/CSS/JS.** After UI edits, kill the running app and relaunch — there's no "reload" on a frameless window.
- **`pythonw.exe` spawns `python.exe` as the actual GUI process.** When killing, terminate *both*: `taskkill /F /IM python.exe && taskkill /F /IM pythonw.exe`. Failing to kill `python.exe` leaves a stale window that ignores all your code changes.
- **Window title is exactly `"WorkClock"`** — used by `EnumWindows` lookups in `_find_workclock_hwnd` for drag and always-on-top. Don't change it.
- **Inline-rendered DOM elements get blown away every 1s by the render loop.** The note input had to move to a modal *outside* the rows container for this reason. If you add new interactive elements, consider whether they survive re-render.
- **`%APPDATA%` from WSL** = `/mnt/c/Users/Xliminal/AppData/Roaming/`. The screenshot tool needs Windows paths (`C:\...`) since it runs under Windows Python.
- **Self-verify with screenshots:** `./venv/Scripts/python.exe tools/capture.py "C:\Users\Xliminal\AppData\Roaming\WorkClock\_screenshot.png"` — saves a PNG of the live window which you can `Read` to actually see what's on screen.

## Out of scope (v1)

- Reporting, summing, or analytics commands. Ask Claude to summarize.
- Git-commit or calendar reconciliation. Done ad-hoc by asking Claude.
- Crash recovery (auto-stop or auto-resume of an interrupted session).
- Notifications (toast/sound).
- Pomodoro / forced breaks.
- Settings UI for always-on-top, idle threshold, or window position.
- Mobile, web, cross-platform.
