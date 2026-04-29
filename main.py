"""WorkClock entry point: pywebview window + state watcher + JS API."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import webview
from filelock import FileLock, Timeout
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from workclock import state, time_worked
from workclock import idle as idle_mod
from workclock.paths import normalize_path

UI_DIR = Path(__file__).parent / "ui"
INDEX = (UI_DIR / "window.html").as_uri()

WINDOW_TITLE = "WorkClock"
ALWAYS_ON_TOP = True
IDLE_THRESHOLD_SECONDS = 15 * 60

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
VK_LBUTTON = 0x01

DEBUG_LOG = Path(os.environ.get("APPDATA", "")) / "WorkClock" / "debug.log"


def _log(msg: str) -> None:
    try:
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")
    except OSError:
        pass


def _now() -> datetime:
    return datetime.now().astimezone()


def _find_workclock_hwnd() -> int:
    matches: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _enum_cb(hwnd, _lparam):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length)
        if WINDOW_TITLE in buf.value:
            matches.append(hwnd)
        return True

    try:
        ctypes.windll.user32.EnumWindows(_enum_cb, 0)
    except OSError:
        return 0
    return matches[0] if matches else 0


class API:
    """JS-callable methods. All return JSON-serializable data."""

    def __init__(self, window_ref):
        self._window_ref = window_ref
        self._pending_session: dict[str, dict] = {}
        self._dragging = False

    def get_state(self) -> dict:
        return state.read_state()

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
                **state.PROJECT_DEFAULTS,
            })

        return state.mutate_state(mut)

    def remove_project(self, name: str) -> dict:
        def mut(s):
            s["projects"] = [p for p in s["projects"] if p["name"] != name]
        return state.mutate_state(mut)

    def start_timer(self, name: str) -> dict:
        """Start a fresh session (idle -> running)."""
        now = _now()

        def mut(s):
            for p in s["projects"]:
                if p["name"] == name and not p["running"] and not p["paused"]:
                    p["running"] = True
                    p["paused"] = False
                    p["started_at"] = now.isoformat()
                    p["session_seconds"] = 0
        return state.mutate_state(mut)

    def pause_timer(self, name: str) -> dict:
        """Freeze the session counter (running -> paused). No log entry."""
        now = _now()

        def mut(s):
            for p in s["projects"]:
                if p["name"] == name and p["running"] and not p["paused"]:
                    started_iso = p.get("started_at")
                    if started_iso:
                        elapsed = max(0, int((now - datetime.fromisoformat(started_iso)).total_seconds()))
                        p["session_seconds"] += elapsed
                    p["running"] = False
                    p["paused"] = True
                    p["started_at"] = None
        return state.mutate_state(mut)

    def resume_timer(self, name: str) -> dict:
        """Continue an in-progress session (paused -> running)."""
        now = _now()

        def mut(s):
            for p in s["projects"]:
                if p["name"] == name and p["paused"]:
                    p["running"] = True
                    p["paused"] = False
                    p["started_at"] = now.isoformat()
        return state.mutate_state(mut)

    def stop_timer(self, name: str) -> dict:
        """End the session (running or paused -> idle). Commit to today/total, reset session counter,
        capture for attach_note. Modal blocks the UI until note is saved."""
        now = _now()
        captured: dict = {}

        def mut(s):
            for p in s["projects"]:
                if p["name"] == name and (p["running"] or p["paused"]):
                    elapsed = int(p.get("session_seconds", 0))
                    started_iso = p.get("started_at")
                    if p["running"] and started_iso:
                        elapsed += max(0, int((now - datetime.fromisoformat(started_iso)).total_seconds()))
                    # Use the *original* session start for log entry: started_at - session_seconds.
                    # If pause/resume happened, started_at points to the most recent resume — back it out.
                    if started_iso:
                        first_start = datetime.fromisoformat(started_iso) - timedelta(seconds=p.get("session_seconds", 0))
                    else:
                        # Paused at the moment of stop: reconstruct from now - elapsed
                        first_start = now - timedelta(seconds=elapsed)
                    captured["started_at"] = first_start.isoformat()
                    captured["stopped_at"] = now.isoformat()
                    captured["project_name"] = p["name"]
                    p["today_seconds"] += elapsed
                    p["total_seconds"] = p.get("total_seconds", 0) + elapsed
                    p["running"] = False
                    p["paused"] = False
                    p["started_at"] = None
                    p["session_seconds"] = 0

        new_state = state.mutate_state(mut)
        if captured:
            self._pending_session[name] = captured
        return new_state

    def pause_all(self) -> dict:
        """Pause every running project at once."""
        now = _now()

        def mut(s):
            for p in s["projects"]:
                if p["running"] and not p["paused"]:
                    started_iso = p.get("started_at")
                    if started_iso:
                        elapsed = max(0, int((now - datetime.fromisoformat(started_iso)).total_seconds()))
                        p["session_seconds"] += elapsed
                    p["running"] = False
                    p["paused"] = True
                    p["started_at"] = None

        return state.mutate_state(mut)

    def resume_all(self) -> dict:
        """Resume every paused project at once."""
        now = _now()

        def mut(s):
            for p in s["projects"]:
                if p["paused"]:
                    p["running"] = True
                    p["paused"] = False
                    p["started_at"] = now.isoformat()

        return state.mutate_state(mut)

    def attach_note(self, name: str, note: str) -> None:
        info = self._pending_session.pop(name, None)
        if not info:
            return
        start = datetime.fromisoformat(info["started_at"])
        stop = datetime.fromisoformat(info["stopped_at"])
        try:
            time_worked.append_session(
                info["project_name"],
                start,
                stop,
                note.strip() if note and note.strip() else None,
            )
        except Exception as e:
            _log(f"append_session failed: {e}")

    def start_drag(self) -> None:
        if self._dragging:
            return
        self._dragging = True
        _log("start_drag")

        def loop():
            hwnd = _find_workclock_hwnd()
            _log(f"drag loop hwnd={hwnd}")
            if not hwnd:
                self._dragging = False
                return
            rect = ctypes.wintypes.RECT()
            pt = ctypes.wintypes.POINT()
            try:
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            except OSError as e:
                _log(f"drag init failed: {e}")
                self._dragging = False
                return

            offset_x = rect.left - pt.x
            offset_y = rect.top - pt.y

            ticks = 0
            while self._dragging:
                if not (ctypes.windll.user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000):
                    break
                try:
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    ctypes.windll.user32.SetWindowPos(
                        hwnd, 0, pt.x + offset_x, pt.y + offset_y, 0, 0,
                        SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
                    )
                except OSError:
                    break
                ticks += 1
                time.sleep(0.008)
            self._dragging = False
            _log(f"drag loop exit ticks={ticks}")

        threading.Thread(target=loop, daemon=True).start()


class StateChangeHandler(FileSystemEventHandler):
    def __init__(self, window_ref):
        self._window_ref = window_ref
        self._last_push = 0.0

    def _push(self, path: str):
        if Path(path).name != "state.json":
            return
        now = time.time()
        if now - self._last_push < 0.2:
            return
        self._last_push = now
        try:
            s = state.read_state()
            _log(f"watchdog push projects={len(s.get('projects', []))}")
            if self._window_ref[0]:
                self._window_ref[0].evaluate_js(f"window.setState({json.dumps(s)})")
        except Exception as e:
            _log(f"watchdog push failed: {e}")

    def on_modified(self, event):
        self._push(event.src_path)

    def on_created(self, event):
        self._push(event.src_path)

    def on_moved(self, event):
        self._push(event.dest_path)


def _idle_loop(window_ref):
    while True:
        time.sleep(30)
        try:
            idle_secs = idle_mod.get_idle_seconds()
            if window_ref[0]:
                window_ref[0].evaluate_js(
                    f"window.setIdle({idle_secs}, {IDLE_THRESHOLD_SECONDS})"
                )
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
    time_worked.ensure_log_exists()

    window_ref = [None]
    api = API(window_ref)

    window = webview.create_window(
        WINDOW_TITLE,
        INDEX,
        js_api=api,
        width=420,
        height=400,
        x=1280,
        y=100,
        on_top=ALWAYS_ON_TOP,
        frameless=True,
        easy_drag=False,
        resizable=False,
        background_color="#0a0a0a",
    )
    window_ref[0] = window

    handler = StateChangeHandler(window_ref)
    observer = Observer()
    observer.schedule(handler, str(state._state_dir()), recursive=False)
    observer.start()

    threading.Thread(target=_idle_loop, args=(window_ref,), daemon=True).start()

    try:
        webview.start()
    finally:
        observer.stop()
        observer.join(timeout=2)
        gui_lock.release()


if __name__ == "__main__":
    main()
