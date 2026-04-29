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
