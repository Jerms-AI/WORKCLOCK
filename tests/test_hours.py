from datetime import datetime
from pathlib import Path

from workclock.hours import append_session, format_duration, format_time


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


def test_creates_file_with_header_when_missing(tmp_path):
    project_dir = tmp_path / "Gloria"
    project_dir.mkdir()
    start = datetime(2026, 4, 29, 9, 15)
    stop = datetime(2026, 4, 29, 11, 43)

    append_session(project_dir, "Gloria", start, stop, note=None)

    content = (project_dir / "hours.md").read_text(encoding="utf-8")
    assert content.startswith("# Hours — Gloria\n")
    assert "## 2026-04-29" in content
    assert "- 09:15–11:43 (2h 28m)" in content


def test_appends_to_existing_day_section(tmp_path):
    project_dir = tmp_path / "Gloria"
    project_dir.mkdir()
    (project_dir / "hours.md").write_text(
        "# Hours — Gloria\n\n## 2026-04-29\n- 09:15–11:43 (2h 28m)\n",
        encoding="utf-8",
    )

    append_session(
        project_dir,
        "Gloria",
        datetime(2026, 4, 29, 13, 30),
        datetime(2026, 4, 29, 15, 0),
        note=None,
    )

    content = (project_dir / "hours.md").read_text(encoding="utf-8")
    lines = content.splitlines()
    assert "- 09:15–11:43 (2h 28m)" in lines
    assert "- 13:30–15:00 (1h 30m)" in lines
    assert content.count("## 2026-04-29") == 1


def test_prepends_new_day_section_above_existing(tmp_path):
    project_dir = tmp_path / "Gloria"
    project_dir.mkdir()
    (project_dir / "hours.md").write_text(
        "# Hours — Gloria\n\n## 2026-04-28\n- 10:00–12:15 (2h 15m)\n",
        encoding="utf-8",
    )

    append_session(
        project_dir,
        "Gloria",
        datetime(2026, 4, 29, 9, 15),
        datetime(2026, 4, 29, 11, 43),
        note=None,
    )

    content = (project_dir / "hours.md").read_text(encoding="utf-8")
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

    content = (project_dir / "hours.md").read_text(encoding="utf-8")
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

    content = (project_dir / "hours.md").read_text(encoding="utf-8")
    assert "## 2026-04-28" in content
    assert "## 2026-04-29" not in content
    assert "- 23:30–00:45 (1h 15m)" in content
