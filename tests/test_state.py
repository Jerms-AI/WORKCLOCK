import json
from datetime import date

from workclock import state as state_mod


def test_read_state_returns_default_when_missing(tmp_appdata):
    s = state_mod.read_state()
    assert s == {"today": date.today().isoformat(), "projects": []}


def test_read_state_round_trips(tmp_appdata):
    initial = {
        "today": date.today().isoformat(),
        "projects": [
            {
                "name": "GLORIA",
                "path": r"C:\Users\Xliminal\Code\PersonalProjects\Gloria",
                "subtitle": None,
                "rate": 0,
                "running": False,
                "paused": False,
                "started_at": None,
                "session_seconds": 0,
                "today_seconds": 0,
                "total_seconds": 0,
            }
        ],
    }
    state_mod._write_state_unsafe(initial)
    s = state_mod.read_state()
    assert s == initial


def test_legacy_state_backfills_new_fields(tmp_appdata):
    """A state.json saved before pause/total fields existed should auto-backfill on read."""
    legacy = {
        "today": date.today().isoformat(),
        "projects": [
            {
                "name": "OLD",
                "path": r"C:\X",
                "running": False,
                "started_at": None,
                "today_seconds": 100,
            }
        ],
    }
    state_mod._write_state_unsafe(legacy)
    s = state_mod.read_state()
    assert s["projects"][0]["rate"] == 0
    assert s["projects"][0]["paused"] is False
    assert s["projects"][0]["session_seconds"] == 0
    assert s["projects"][0]["total_seconds"] == 0
    assert s["projects"][0]["today_seconds"] == 100  # preserved


def test_today_rollover_resets_today_seconds(tmp_appdata):
    initial = {
        "today": "2020-01-01",
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

    on_disk = state_mod.read_state()
    assert on_disk["projects"][0]["name"] == "WTF_IS_PHYSICS"


def test_atomic_write_no_partial_file_on_disk(tmp_appdata):
    state_mod.mutate_state(lambda s: s["projects"].append(
        {"name": "X", "path": r"C:\x", "running": False, "started_at": None, "today_seconds": 0}
    ))
    appdata = tmp_appdata / "WorkClock"
    assert (appdata / "state.json").exists()
    assert not (appdata / "state.json.tmp").exists()
