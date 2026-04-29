import json
from datetime import datetime, timezone

from workclock.time_worked import append_session, ensure_log_exists, log_path


def test_ensure_log_creates_empty_array(tmp_appdata):
    ensure_log_exists()
    assert json.loads(log_path().read_text(encoding="utf-8")) == []


def test_ensure_log_does_not_overwrite_existing(tmp_appdata):
    log_path().parent.mkdir(parents=True, exist_ok=True)
    log_path().write_text('[{"project": "X"}]', encoding="utf-8")

    ensure_log_exists()

    assert json.loads(log_path().read_text(encoding="utf-8")) == [{"project": "X"}]


def test_append_creates_file_when_missing(tmp_appdata):
    start = datetime(2026, 4, 29, 11, 8, 16, tzinfo=timezone.utc)
    stop = datetime(2026, 4, 29, 11, 30, 45, tzinfo=timezone.utc)

    append_session("ASANDRA_POC", start, stop, note="auth bug")

    entries = json.loads(log_path().read_text(encoding="utf-8"))
    assert len(entries) == 1
    e = entries[0]
    assert e["project"] == "ASANDRA_POC"
    assert e["date"] == "2026-04-29"
    assert e["start"] == "2026-04-29T11:08:16+00:00"
    assert e["stop"] == "2026-04-29T11:30:45+00:00"
    assert e["duration_seconds"] == 22 * 60 + 29
    assert e["note"] == "auth bug"


def test_append_adds_to_existing_array(tmp_appdata):
    append_session(
        "ASANDRA_POC",
        datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 28, 10, 0, tzinfo=timezone.utc),
        note=None,
    )
    append_session(
        "GLORIA",
        datetime(2026, 4, 29, 11, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 29, 11, 30, tzinfo=timezone.utc),
        note="follow-up",
    )

    entries = json.loads(log_path().read_text(encoding="utf-8"))
    assert len(entries) == 2
    assert entries[0]["project"] == "ASANDRA_POC"
    assert entries[0]["note"] is None
    assert entries[1]["project"] == "GLORIA"
    assert entries[1]["note"] == "follow-up"


def test_empty_or_whitespace_note_normalized_to_null(tmp_appdata):
    append_session(
        "X",
        datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 29, 9, 5, tzinfo=timezone.utc),
        note="",
    )

    entries = json.loads(log_path().read_text(encoding="utf-8"))
    assert entries[0]["note"] is None
