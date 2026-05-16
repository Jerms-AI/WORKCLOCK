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


def test_summary_amd_worked_example(tmp_appdata):
    _write(tmp_appdata, SESSIONS, PAYMENTS)
    s = B.summary("amd", today=date(2026, 5, 16))

    poc = s["projects"]["ASANDRA_POC"]
    assert poc["paid_amount"] == 410.50
    assert poc["outstanding_hours"] == 1.0  # only Week4 3600s
    assert poc["outstanding_amount"] == 25.0

    app = s["projects"]["ASANDRA_APP"]
    assert app["paid_amount"] == 0.0
    assert app["outstanding_hours"] == 2.0  # Week5 only (Week6 open, excluded)

    assert s["paid_total"] == 1101.50
    # closed weeks 4+5: 1.5h*25 + (2h+1h)*25 = 37.5 + 75 = 112.5
    assert s["outstanding_total"] == 112.50
    assert s["open_week"]["num"] == 6
    assert s["open_week"]["hours"] == 0.25
    assert s["paid_caption"] == "Weeks 1–3 · Apr 13 – May 3 · settled May 8 ✓"
    assert s["outstanding_caption"] == "Weeks 4–5 · May 4 – May 15"


def test_summary_gloria_no_payments(tmp_appdata):
    _write(tmp_appdata, [
        {"project": "GLORIA", "date": "2026-05-05", "duration_seconds": 3600},
    ], {"payments": []})
    s = B.summary("gloria", today=date(2026, 5, 16))
    assert s["paid_total"] == 0.0
    assert s["paid_caption"] is None
    assert s["projects"]["GLORIA"]["outstanding_amount"] == 55.0


from billing import render as R


def test_render_full_contains_key_fields(tmp_appdata):
    _write(tmp_appdata, SESSIONS, PAYMENTS)
    s = B.summary("amd", today=date(2026, 5, 16))
    html = R.render(s, "amd", mode="full")
    assert "<!DOCTYPE html>" in html
    assert "Weeks 1–3 · Apr 13 – May 3 · settled May 8 ✓" in html
    assert "Weeks 4–5 · May 4 – May 15" in html
    assert "ASANDRA_POC" in html
    assert "$112.50" in html  # outstanding total
    assert "Week 6" in html   # open week line
    assert "Paid (invoiced)" in html
    assert "May 16, 2026" in html


def test_render_outstanding_only_omits_paid(tmp_appdata):
    _write(tmp_appdata, [
        {"project": "GLORIA", "date": "2026-05-05", "duration_seconds": 3600}],
        {"payments": []})
    s = B.summary("gloria", today=date(2026, 5, 16))
    html = R.render(s, "gloria", mode="outstanding-only")
    assert "Paid (invoiced)" not in html
    assert "GLORIA" in html


from billing import generate as G


def test_generate_writes_html(tmp_appdata, tmp_path):
    _write(tmp_appdata, SESSIONS, PAYMENTS)
    out = tmp_path / "amd.html"
    rc = G.main(["amd", "--out", str(out), "--today", "2026-05-16"])
    assert rc == 0
    html = out.read_text(encoding="utf-8")
    assert "Billing Summary" in html
    assert "$112.50" in html


def test_generate_unknown_client_errors(tmp_appdata, tmp_path):
    _write(tmp_appdata, [])
    rc = G.main(["acme", "--out", str(tmp_path / "x.html"),
                 "--today", "2026-05-16"])
    assert rc != 0


def test_summary_uses_client_rate_when_project_missing_from_state(tmp_appdata):
    # state.json omits ASANDRA_POC entirely (retired project)
    _write(tmp_appdata, SESSIONS, PAYMENTS, projects=[
        {"name": "ASANDRA_APP", "rate": 25},
        {"name": "SITEREVAMP", "rate": 25},
    ])
    s = B.summary("amd", today=date(2026, 5, 16))
    poc = s["projects"]["ASANDRA_POC"]
    assert poc["outstanding_hours"] == 1.0          # Week 4 only
    assert poc["outstanding_amount"] == 25.0        # 1.0h * $25 client fallback (not $0)


def test_generate_warns_on_zero_duration(tmp_appdata, tmp_path, capsys):
    _write(tmp_appdata, [
        {"project": "SITEREVAMP", "date": "2026-05-08", "duration_seconds": 0,
         "note": "df"},
        {"project": "SITEREVAMP", "date": "2026-05-08",
         "duration_seconds": 3600, "note": "real"},
    ], {"payments": []})
    rc = G.main(["amd", "--out", str(tmp_path / "a.html"),
                 "--today", "2026-05-16"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARNING" in err and "zero/negative" in err


def test_render_dashboard_has_cards_and_links(tmp_appdata):
    _write(tmp_appdata, SESSIONS, PAYMENTS)
    amd = B.summary("amd", today=date(2026, 5, 16))
    _write(tmp_appdata, [
        {"project": "GLORIA", "date": "2026-05-05", "duration_seconds": 3600}],
        {"payments": []})
    glo = B.summary("gloria", today=date(2026, 5, 16))
    html = R.render_dashboard({"gloria": glo, "amd": amd}, "May 16, 2026")
    assert "<!DOCTYPE html>" in html
    assert "Cyber Canvas Collective" in html
    assert "As of May 16, 2026" in html
    assert "AMD International" in html
    assert "ASANDRA_POC · ASANDRA_APP · SITEREVAMP" in html
    assert "$112.50" in html
    assert "$1,101.50 paid ✓" in html
    assert 'href="AMD_billing_summary.html"' in html
    assert "Gloria" in html
    assert "not yet invoiced" in html
    assert 'href="GLORIA_billing_summary.html"' in html


def test_generate_dashboard_writes_all(tmp_appdata, tmp_path):
    _write(tmp_appdata, SESSIONS, PAYMENTS)
    dash = tmp_path / "dashboard.html"
    rc = G.main(["dashboard", "--out", str(dash), "--today", "2026-05-16"])
    assert rc == 0
    assert (tmp_path / "AMD_billing_summary.html").exists()
    assert (tmp_path / "GLORIA_billing_summary.html").exists()
    d = dash.read_text(encoding="utf-8")
    assert "Cyber Canvas Collective" in d
    assert 'href="AMD_billing_summary.html"' in d
    assert 'href="GLORIA_billing_summary.html"' in d


def test_render_dashboard_zero_outstanding_still_renders():
    zero = {
        "client": "gloria", "projects": {"GLORIA": {}},
        "paid_total": 0.0, "outstanding_total": 0.0,
        "outstanding_hours_total": 0.0,
        "outstanding_caption": "No closed weeks yet",
        "generated": "May 16, 2026",
    }
    html = R.render_dashboard({"gloria": zero}, "May 16, 2026")
    assert "Gloria" in html
    assert "$0.00" in html
    assert 'href="GLORIA_billing_summary.html"' in html
