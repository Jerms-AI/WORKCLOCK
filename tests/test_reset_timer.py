import json
from datetime import date

from workclock import state as state_mod
from workclock.time_worked import log_path


def _seed_running(started_at="2026-05-15T10:00:00-04:00", session_seconds=120):
    state_mod._write_state_unsafe(
        {
            "today": date.today().isoformat(),
            "projects": [
                {
                    "name": "ASANDRA_APP",
                    "path": r"C:\x",
                    "subtitle": None,
                    "rate": 25,
                    "running": True,
                    "paused": False,
                    "started_at": started_at,
                    "session_seconds": session_seconds,
                    "today_seconds": 600,
                    "total_seconds": 9000,
                }
            ],
        }
    )


def test_reset_timer_commits_exact_duration(tmp_appdata):
    from main import API

    _seed_running()
    api = API([None])

    api.reset_timer("ASANDRA_APP", 4 * 3600 + 20 * 60, "manual entry")

    p = state_mod.read_state()["projects"][0]
    assert p["today_seconds"] == 600 + 15600
    assert p["total_seconds"] == 9000 + 15600
    assert p["running"] is False
    assert p["paused"] is False
    assert p["started_at"] is None
    assert p["session_seconds"] == 0


def test_reset_timer_logs_session_with_duration(tmp_appdata):
    from main import API

    _seed_running()
    api = API([None])

    api.reset_timer("ASANDRA_APP", 100 * 60, "note here")

    entries = json.loads(log_path().read_text(encoding="utf-8"))
    assert len(entries) == 1
    e = entries[0]
    assert e["project"] == "ASANDRA_APP"
    assert e["duration_seconds"] == 6000
    assert e["note"] == "note here"
    # stop anchored to now, start = now - duration
    from datetime import datetime

    start = datetime.fromisoformat(e["start"])
    stop = datetime.fromisoformat(e["stop"])
    assert abs((stop - start).total_seconds() - 6000) < 2


def test_reset_timer_ignores_idle_project(tmp_appdata):
    from main import API

    state_mod._write_state_unsafe(
        {
            "today": date.today().isoformat(),
            "projects": [
                {
                    "name": "ASANDRA_APP",
                    "path": r"C:\x",
                    "subtitle": None,
                    "rate": 25,
                    "running": False,
                    "paused": False,
                    "started_at": None,
                    "session_seconds": 0,
                    "today_seconds": 600,
                    "total_seconds": 9000,
                }
            ],
        }
    )
    api = API([None])

    api.reset_timer("ASANDRA_APP", 3600, None)

    p = state_mod.read_state()["projects"][0]
    assert p["today_seconds"] == 600
    assert p["total_seconds"] == 9000
    assert not log_path().exists() or json.loads(log_path().read_text()) == []
