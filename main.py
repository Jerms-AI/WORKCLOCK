"""WorkClock entry point: pywebview window + state watcher + JS API."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
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
        self._pending_session = {}

    def get_state(self) -> dict:
        return _state_with_recovery_flags()

    def get_settings(self) -> dict:
        return settings.read_settings()

    def update_setting(self, key: str, value) -> dict:
        s = settings.read_settings()
        s[key] = value
        settings.write_settings(s)
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
        info = self._pending_session.pop(name, None)
        if not info:
            return
        start = datetime.fromisoformat(info["started_at"])
        stop = datetime.fromisoformat(info["stopped_at"])

        if trim_to_idle:
            idle_secs = idle.get_idle_seconds()
            trim_to = _now() - timedelta(seconds=idle_secs)
            if trim_to > start:
                old_elapsed = int((stop - start).total_seconds())
                new_elapsed = int((trim_to - start).total_seconds())
                delta = new_elapsed - old_elapsed

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
        def mut(s):
            pass
        state.mutate_state(mut)
        return _state_with_recovery_flags()


class StateChangeHandler(FileSystemEventHandler):
    def __init__(self, window_ref):
        self._window_ref = window_ref
        self._last_push = 0.0

    def on_modified(self, event):
        if Path(event.src_path).name != "state.json":
            return
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

    handler = StateChangeHandler(window_ref)
    observer = Observer()
    observer.schedule(handler, str(state._state_dir()), recursive=False)
    observer.start()

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
