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


def test_week_end_friday():
    # Mon 2026-05-04 -> Fri 2026-05-08
    assert B.week_end_friday(date(2026, 5, 4)) == date(2026, 5, 8)
    # Sat 2026-05-16 rolls forward to Fri 2026-05-22
    assert B.week_end_friday(date(2026, 5, 16)) == date(2026, 5, 22)
    # A Friday maps to itself
    assert B.week_end_friday(date(2026, 5, 15)) == date(2026, 5, 15)


def test_paid_week_count_apr13_may3_is_3():
    assert B.paid_week_count(date(2026, 4, 13), date(2026, 5, 3)) == 3


SESSIONS = [
    # paid period (<= 2026-05-03) — ignored by billing_weeks
    {"project": "SITEREVAMP", "date": "2026-04-30", "duration_seconds": 3600},
    # Week 4: May 4-8 (Mon-Fri, stub)
    {"project": "ASANDRA_POC", "date": "2026-05-04", "duration_seconds": 3600},
    {"project": "SITEREVAMP", "date": "2026-05-08", "duration_seconds": 1800},
    # Week 5: May 9-15 (Sat-Fri) — Sat work rolls into this week
    {"project": "ASANDRA_APP", "date": "2026-05-09", "duration_seconds": 7200},
    {"project": "SITEREVAMP", "date": "2026-05-15", "duration_seconds": 3600},
    # Week 6: May 16-22 — open (today = 2026-05-16)
    {"project": "ASANDRA_APP", "date": "2026-05-16", "duration_seconds": 900},
]
PAYMENTS = {"payments": [
    {"project": "ASANDRA_POC", "period_start": "2026-04-13",
     "period_end": "2026-05-03", "paid_on": "2026-05-08",
     "hours": 16.42, "rate": 25, "amount": 410.50, "note": "init"},
    {"project": "SITEREVAMP", "period_start": "2026-04-13",
     "period_end": "2026-05-03", "paid_on": "2026-05-08",
     "hours": 27.64, "rate": 25, "amount": 691.00, "note": "init"},
]}


def test_billing_weeks_buckets_and_numbers(tmp_appdata):
    _write(tmp_appdata, SESSIONS, PAYMENTS)
    weeks = B.billing_weeks("amd", today=date(2026, 5, 16))
    assert [w.num for w in weeks] == [4, 5, 6]
    w4, w5, w6 = weeks
    assert (w4.start, w4.end) == (date(2026, 5, 4), date(2026, 5, 8))
    assert (w5.start, w5.end) == (date(2026, 5, 9), date(2026, 5, 15))
    assert (w6.start, w6.end) == (date(2026, 5, 16), date(2026, 5, 22))
    assert w4.closed and w5.closed and not w6.closed
    # Sat 2026-05-09 work landed in week 5, not week 4
    assert w5.by_project["ASANDRA_APP"] == 2.0
    assert w5.total_hours == 3.0
    assert w5.total_amount == 3.0 * 25
    assert w4.total_hours == 1.5  # 3600 + 1800 s
    assert w4.total_amount == 1.5 * 25
