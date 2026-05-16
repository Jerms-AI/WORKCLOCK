import json
from datetime import date

from billing import billing as B


def _write(appdata, time_worked, billing=None, projects=None):
    d = appdata / "WorkClock"
    d.mkdir(parents=True, exist_ok=True)
    (d / "Time_Worked.json").write_text(json.dumps(time_worked), encoding="utf-8")
    if billing is not None:
        (d / "billing.json").write_text(json.dumps(billing), encoding="utf-8")
    state = {
        "today": "2026-05-16",
        "projects": projects
        or [
            {"name": "ASANDRA_POC", "rate": 25},
            {"name": "ASANDRA_APP", "rate": 25},
            {"name": "SITEREVAMP", "rate": 25},
            {"name": "GLORIA", "rate": 55},
        ],
    }
    (d / "state.json").write_text(json.dumps(state), encoding="utf-8")


def test_load_payments_missing_file_returns_empty(tmp_appdata):
    _write(tmp_appdata, [])
    assert B.load_payments() == []


def test_load_sessions_and_rate(tmp_appdata):
    _write(
        tmp_appdata,
        [{"project": "SITEREVAMP", "date": "2026-05-05",
          "duration_seconds": 3600, "note": "x"}],
    )
    assert B.load_sessions()[0]["project"] == "SITEREVAMP"
    assert B.project_rate("SITEREVAMP") == 25
    assert B.project_rate("GLORIA") == 55
