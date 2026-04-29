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
