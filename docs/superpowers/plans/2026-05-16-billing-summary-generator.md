# Billing Summary Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A repeatable CLI that turns local WorkClock data into a per-client billing-summary HTML, split into Paid vs Outstanding by Friday-ending billing weeks.

**Architecture:** Three small modules in a new `billing/` package: `billing.py` (pure date/money logic, no rendering), `render.py` (HTML only, no logic), `generate.py` (thin CLI). Reads the existing `%APPDATA%\WorkClock\` JSON files read-only; never mutates them. Mirrors WorkClock's existing pure-module + thin-glue split.

**Tech Stack:** Python 3.13 stdlib only (`json`, `datetime`, `argparse`, `dataclasses`). pytest with the existing `tmp_appdata` fixture.

---

## Reference: spec

`docs/superpowers/specs/2026-05-16-billing-summary-design.md`. Re-read the
"Billing-week model" and "Worked example" sections before Task 3.

## File Structure

- Create `billing/__init__.py` — empty package marker.
- Create `billing/billing.py` — data loading, week bucketing, summary aggregation.
- Create `billing/render.py` — `render(summary, client, mode) -> str` HTML.
- Create `billing/generate.py` — CLI entry point.
- Create `tests/test_billing.py` — pytest, uses `tmp_appdata`.
- Create `billing/DEVDOC.md` — operating doc.
- Create `CLAUDE.md` (repo root) — session-start reference.

Established patterns to follow (already in repo):
- `workclock/time_worked.py` computes its dir as `Path(os.environ["APPDATA"]) / "WorkClock"`. Replicate this 3-line pattern in `billing.py` (the codebase already repeats it per-module rather than sharing — follow that).
- `tests/conftest.py` provides `tmp_appdata` (monkeypatches `APPDATA` to a temp dir). All tests use it.
- `workclock/state.py` `read_state()` returns `{"today":..., "projects":[{name,rate,...}]}`.
- Test command: `./venv/Scripts/python.exe -m pytest tests/ -v`

---

### Task 1: Package skeleton + data loaders

**Files:**
- Create: `billing/__init__.py`
- Create: `billing/billing.py`
- Test: `tests/test_billing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_billing.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'billing'`

- [ ] **Step 3: Write minimal implementation**

```python
# billing/__init__.py
```

(empty file)

```python
# billing/billing.py
"""Billing logic: load WorkClock data, bucket outstanding work into
Friday-ending billing weeks, aggregate per-client paid vs outstanding.

Reads %APPDATA%\\WorkClock\\{Time_Worked.json,billing.json,state.json}
READ-ONLY. Never mutates source files.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

CLIENTS: dict[str, list[str]] = {
    "amd": ["ASANDRA_POC", "ASANDRA_APP", "SITEREVAMP"],
    "gloria": ["GLORIA"],
}

_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt(d: date) -> str:
    return f"{_MON[d.month]} {d.day}"


def _dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA env var is not set")
    return Path(appdata) / "WorkClock"


def _read_json(name: str, default):
    p = _dir() / name
    if not p.exists():
        return default
    txt = p.read_text(encoding="utf-8").strip()
    if not txt:
        return default
    return json.loads(txt)


def load_sessions() -> list[dict]:
    return _read_json("Time_Worked.json", [])


def load_payments() -> list[dict]:
    data = _read_json("billing.json", {"payments": []})
    return data.get("payments", []) if isinstance(data, dict) else []


def project_rate(project: str) -> int:
    state = _read_json("state.json", {"projects": []})
    for p in state.get("projects", []):
        if p.get("name") == project:
            return int(p.get("rate", 0))
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add billing/__init__.py billing/billing.py tests/test_billing.py
git commit -m "feat: billing package skeleton + data loaders"
```

---

### Task 2: Friday-week date helpers

**Files:**
- Modify: `billing/billing.py`
- Test: `tests/test_billing.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_billing.py
def test_week_end_friday():
    # Mon 2026-05-04 -> Fri 2026-05-08
    assert B.week_end_friday(date(2026, 5, 4)) == date(2026, 5, 8)
    # Sat 2026-05-16 rolls forward to Fri 2026-05-22
    assert B.week_end_friday(date(2026, 5, 16)) == date(2026, 5, 22)
    # A Friday maps to itself
    assert B.week_end_friday(date(2026, 5, 15)) == date(2026, 5, 15)


def test_paid_week_count_apr13_may3_is_3():
    assert B.paid_week_count(date(2026, 4, 13), date(2026, 5, 3)) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k "friday or paid_week_count" -v`
Expected: FAIL — `AttributeError: module 'billing.billing' has no attribute 'week_end_friday'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to billing/billing.py

def week_end_friday(d: date) -> date:
    """The Friday on or after d (weekday(): Mon=0 .. Fri=4 .. Sun=6)."""
    return d + timedelta(days=(4 - d.weekday()) % 7)


def paid_week_count(period_start: date, period_end: date) -> int:
    """Number of 7-day weeks the paid invoice spans (inclusive, ceil)."""
    days = (period_end - period_start).days + 1
    return (days + 6) // 7
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k "friday or paid_week_count" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add billing/billing.py tests/test_billing.py
git commit -m "feat: Friday-week date helpers"
```

---

### Task 3: `billing_weeks()` — bucket outstanding work

**Files:**
- Modify: `billing/billing.py`
- Test: `tests/test_billing.py`

Behavior: outstanding = sessions strictly after the latest paid `period_end`
for the client. Bucket each by `week_end_friday(session_date)`. Week number
starts at `paid_week_count + 1`. A week is `closed` when its Friday `< today`.
First week's `start` is clamped to `paid_end + 1` (the one-time short stub).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_billing.py
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
    assert w4.total_hours == 1.5  # 3600 + 1800 s
    assert w4.total_amount == 1.5 * 25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k billing_weeks -v`
Expected: FAIL — `AttributeError: ... has no attribute 'billing_weeks'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to billing/billing.py

@dataclass
class Week:
    num: int
    start: date
    end: date  # a Friday
    closed: bool
    by_project: dict[str, float] = field(default_factory=dict)  # hours
    total_hours: float = 0.0
    total_amount: float = 0.0


def _parse(ds: str) -> date:
    y, m, d = (int(x) for x in ds.split("-"))
    return date(y, m, d)


def _client_paid_period(client: str, payments: list[dict]):
    """(period_start, period_end, paid_on) across the client's projects, or None."""
    names = set(CLIENTS[client])
    rel = [p for p in payments if p.get("project") in names]
    if not rel:
        return None
    ps = min(_parse(p["period_start"]) for p in rel)
    pe = max(_parse(p["period_end"]) for p in rel)
    po = max(_parse(p["paid_on"]) for p in rel)
    return ps, pe, po


def billing_weeks(client: str, today: date) -> list[Week]:
    names = set(CLIENTS[client])
    payments = load_payments()
    period = _client_paid_period(client, payments)
    paid_end = period[1] if period else None
    base_num = paid_week_count(period[0], period[1]) if period else 0

    buckets: dict[date, dict[str, float]] = {}
    for s in load_sessions():
        if s.get("project") not in names:
            continue
        d = _parse(s["date"])
        if paid_end is not None and d <= paid_end:
            continue
        we = week_end_friday(d)
        proj = s["project"]
        hrs = s.get("duration_seconds", 0) / 3600.0
        buckets.setdefault(we, {}).setdefault(proj, 0.0)
        buckets[we][proj] += hrs

    weeks: list[Week] = []
    for i, we in enumerate(sorted(buckets)):
        start = we - timedelta(days=6)
        if paid_end is not None and start <= paid_end:
            start = paid_end + timedelta(days=1)
        by_project = buckets[we]
        total_hours = sum(by_project.values())
        total_amount = sum(h * project_rate(p) for p, h in by_project.items())
        weeks.append(Week(
            num=base_num + i + 1,
            start=start,
            end=we,
            closed=we < today,
            by_project=by_project,
            total_hours=round(total_hours, 4),
            total_amount=round(total_amount, 2),
        ))
    return weeks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k billing_weeks -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add billing/billing.py tests/test_billing.py
git commit -m "feat: billing_weeks() Friday bucketing with stub + numbering"
```

---

### Task 4: `summary()` — per-client paid vs outstanding aggregate

**Files:**
- Modify: `billing/billing.py`
- Test: `tests/test_billing.py`

Outstanding sums use **closed weeks only**. The single open week (if any)
is reported separately and excluded from billable totals.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_billing.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k summary -v`
Expected: FAIL — `AttributeError: ... has no attribute 'summary'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to billing/billing.py

def summary(client: str, today: date) -> dict:
    names = CLIENTS[client]
    payments = load_payments()
    period = _client_paid_period(client, payments)
    weeks = billing_weeks(client, today)
    closed = [w for w in weeks if w.closed]
    open_weeks = [w for w in weeks if not w.closed]

    projects: dict[str, dict] = {}
    for name in names:
        paid_amount = round(sum(
            p.get("amount", 0.0) for p in payments
            if p.get("project") == name), 2)
        paid_hours = round(sum(
            p.get("hours", 0.0) for p in payments
            if p.get("project") == name), 2)
        out_h = round(sum(w.by_project.get(name, 0.0) for w in closed), 4)
        projects[name] = {
            "paid_hours": paid_hours,
            "paid_amount": paid_amount,
            "outstanding_hours": round(out_h, 2),
            "outstanding_amount": round(out_h * project_rate(name), 2),
        }

    paid_total = round(sum(p["paid_amount"] for p in projects.values()), 2)
    outstanding_total = round(sum(w.total_amount for w in closed), 2)
    outstanding_hours_total = round(sum(w.total_hours for w in closed), 2)

    if period:
        ps, pe, po = period
        pwc = paid_week_count(ps, pe)
        paid_caption = (f"Weeks 1–{pwc} · {fmt(ps)} – {fmt(pe)} "
                        f"· settled {fmt(po)} ✓")
    else:
        paid_caption = None

    if closed:
        n0, n1 = closed[0].num, closed[-1].num
        wlabel = f"Week {n0}" if n0 == n1 else f"Weeks {n0}–{n1}"
        outstanding_caption = (
            f"{wlabel} · {fmt(closed[0].start)} – {fmt(closed[-1].end)}")
    else:
        outstanding_caption = "No closed weeks yet"

    open_week = None
    if open_weeks:
        w = open_weeks[0]
        open_week = {"num": w.num, "hours": round(w.total_hours, 2),
                     "amount": w.total_amount,
                     "range": f"{fmt(w.start)} – {fmt(w.end)}"}

    return {
        "client": client,
        "projects": projects,
        "paid_total": paid_total,
        "outstanding_total": outstanding_total,
        "outstanding_hours_total": outstanding_hours_total,
        "paid_caption": paid_caption,
        "outstanding_caption": outstanding_caption,
        "open_week": open_week,
        "generated": fmt(today),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k summary -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add billing/billing.py tests/test_billing.py
git commit -m "feat: summary() per-client paid vs outstanding aggregate"
```

---

### Task 5: `render.py` — HTML output

**Files:**
- Create: `billing/render.py`
- Test: `tests/test_billing.py`

Reuse the approved Amber aesthetic from `/mnt/c/Users/Xliminal/AMD_billing_summary.html`.
`mode="outstanding-only"` drops the Paid column entirely.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_billing.py
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


def test_render_outstanding_only_omits_paid(tmp_appdata):
    _write(tmp_appdata, [
        {"project": "GLORIA", "date": "2026-05-05", "duration_seconds": 3600}],
        {"payments": []})
    s = B.summary("gloria", today=date(2026, 5, 16))
    html = R.render(s, "gloria", mode="outstanding-only")
    assert "Paid (invoiced)" not in html
    assert "GLORIA" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k render -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'billing.render'`

- [ ] **Step 3: Write minimal implementation**

```python
# billing/render.py
"""Render a billing summary() dict to a self-contained HTML string.

Amber editorial aesthetic (Fraunces + Inter, parchment #f6f4ef,
terracotta #c2410c, paid-green #5a7d54). No business logic here.
"""
from __future__ import annotations

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#f6f4ef;color:#1f1c18;font-family:'Inter',-apple-system,
BlinkMacSystemFont,'Segoe UI',sans-serif;display:flex;justify-content:center;
padding:64px 24px;-webkit-font-smoothing:antialiased}
.sheet{width:100%;max-width:640px}
header{margin-bottom:40px}
.eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;
color:#c2410c;font-weight:600;margin-bottom:10px}
h1{font-family:'Fraunces',Georgia,serif;font-size:38px;font-weight:600;
letter-spacing:-.01em}
.date{color:#6b6358;font-size:14px;margin-top:8px}
table{width:100%;border-collapse:collapse;margin-top:8px}
th{text-align:left;font-size:12px;letter-spacing:.1em;text-transform:uppercase;
color:#6b6358;font-weight:600;padding:14px 16px;border-bottom:2px solid #ddd6c9}
th .cap{display:block;text-transform:none;letter-spacing:0;font-weight:500;
font-size:11px;color:#6b6358;margin-top:6px}
th.num,td.num{text-align:right}
td{padding:18px 16px;border-bottom:1px solid #ddd6c9;font-size:16px}
td.project{font-weight:600}
.amount{font-variant-numeric:tabular-nums;white-space:nowrap}
.hours{color:#6b6358;font-size:14px}
tr.total td{border-bottom:none;border-top:2px solid #1f1c18;padding-top:20px;
font-weight:700;font-size:17px}
.paid-tag{color:#5a7d54;font-weight:600}
.out-amt{color:#c2410c;font-weight:700}
.openwk{margin-top:18px;font-size:13px;color:#6b6358;font-style:italic}
footer{margin-top:36px;color:#6b6358;font-size:13px;line-height:1.6}
"""

_TITLES = {"amd": "AMD International", "gloria": "Gloria"}


def _money(v: float) -> str:
    return f"${v:,.2f}"


def render(summary: dict, client: str, mode: str = "full") -> str:
    full = mode != "outstanding-only"
    s = summary
    title = _TITLES.get(client, client.upper())

    head_paid = ""
    if full:
        cap = s["paid_caption"] or ""
        head_paid = (f'<th class="num">Paid (invoiced)'
                     f'<span class="cap">{cap}</span></th>')
    head_out = (f'<th class="num">Outstanding'
                f'<span class="cap">{s["outstanding_caption"]}</span></th>')

    rows = ""
    for name, p in s["projects"].items():
        paid_cell = ""
        if full:
            if p["paid_amount"]:
                paid_cell = (
                    f'<td class="num amount"><span class="hours">'
                    f'{p["paid_hours"]:.2f} h</span><br>{_money(p["paid_amount"])}'
                    f' <span class="paid-tag">✓</span></td>')
            else:
                paid_cell = '<td class="num amount"><span class="hours">—</span></td>'
        out_cell = (
            f'<td class="num amount"><span class="hours">'
            f'{p["outstanding_hours"]:.2f} h</span><br>'
            f'<span class="out-amt">{_money(p["outstanding_amount"])}</span></td>')
        rows += (f'<tr><td class="project">{name}</td>'
                 f'{paid_cell}{out_cell}</tr>')

    total_paid = ""
    if full:
        total_paid = (f'<td class="num amount">{_money(s["paid_total"])} '
                      f'<span class="paid-tag">✓</span></td>')
    total_row = (
        f'<tr class="total"><td>Total</td>{total_paid}'
        f'<td class="num amount"><span class="hours">'
        f'{s["outstanding_hours_total"]:.2f} h</span><br>'
        f'<span class="out-amt">{_money(s["outstanding_total"])}</span></td></tr>')

    openwk = ""
    if s["open_week"]:
        ow = s["open_week"]
        openwk = (f'<div class="openwk">Week {ow["num"]} ({ow["range"]}) '
                  f'in progress — {ow["hours"]:.2f} h, not yet billed.</div>')

    colcount = 3 if full else 2
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title} — Billing Summary</title>
<style>{_CSS}</style>
</head>
<body>
  <div class="sheet">
    <header>
      <div class="eyebrow">{title}</div>
      <h1>Billing Summary</h1>
      <div class="date">As of {s["generated"]}, 2026</div>
    </header>
    <table>
      <thead><tr><th>Project</th>{head_paid}{head_out}</tr></thead>
      <tbody>{rows}{total_row}</tbody>
    </table>
    {openwk}
    <footer>
      Paid amounts reflect received payments. Outstanding reflects closed
      Friday-ending billing weeks not yet invoiced. ({colcount}-col)
    </footer>
  </div>
</body>
</html>
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k render -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add billing/render.py tests/test_billing.py
git commit -m "feat: render() billing summary HTML (Amber aesthetic)"
```

---

### Task 6: `generate.py` — CLI

**Files:**
- Create: `billing/generate.py`
- Test: `tests/test_billing.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_billing.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k generate -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'billing.generate'`

- [ ] **Step 3: Write minimal implementation**

```python
# billing/generate.py
"""CLI: python -m billing.generate <client> [--mode ...] [--out ...] [--today ...]

Examples:
  python -m billing.generate amd
  python -m billing.generate gloria --mode outstanding-only
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from billing import billing as B
from billing import render as R

_DEFAULT_MODE = {"amd": "full", "gloria": "outstanding-only"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="billing.generate")
    ap.add_argument("client")
    ap.add_argument("--mode", choices=["full", "outstanding-only"], default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--today", default=None,
                    help="YYYY-MM-DD override (default: real today)")
    args = ap.parse_args(argv)

    client = args.client.lower()
    if client not in B.CLIENTS:
        print(f"Unknown client {client!r}. Valid: {', '.join(B.CLIENTS)}",
              file=sys.stderr)
        return 2

    if args.today:
        y, m, d = (int(x) for x in args.today.split("-"))
        today = date(y, m, d)
    else:
        today = date.today()

    mode = args.mode or _DEFAULT_MODE.get(client, "full")
    out = args.out or f"/mnt/c/Users/Xliminal/{client.upper()}_billing_summary.html"

    s = B.summary(client, today=today)
    html = R.render(s, client, mode=mode)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out}  (outstanding {s['outstanding_total']:,.2f}, "
          f"paid {s['paid_total']:,.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -v`
Expected: PASS (entire file green)

- [ ] **Step 5: Commit**

```bash
git add billing/generate.py tests/test_billing.py
git commit -m "feat: billing generate CLI"
```

---

### Task 7: Docs — DEVDOC.md + CLAUDE.md

**Files:**
- Create: `billing/DEVDOC.md`
- Create: `CLAUDE.md`

- [ ] **Step 1: Write `billing/DEVDOC.md`**

```markdown
# Billing Generator — DEVDOC

Turns WorkClock data into a per-client billing-summary HTML.

## Run

    ./venv/Scripts/python.exe -m billing.generate amd
    ./venv/Scripts/python.exe -m billing.generate gloria

Output default: `C:\Users\Xliminal\<CLIENT>_billing_summary.html`
(`/mnt/c/Users/Xliminal/...` from WSL). Override with `--out`.
`--today YYYY-MM-DD` reproduces a past bill. `--mode full|outstanding-only`
(default: amd=full, gloria=outstanding-only).

## Week model

A billing week is the 7 days ending **Friday EOD** (Sat→Fri). Weekend work
rolls into the upcoming Friday's week. A week is billable once its Friday has
passed; the current open week is shown but not billed. Weeks 1–N are the
historical paid invoice (by date range, not bucketed); outstanding weeks are
numbered from N+1. Week 4 is a one-time short stub (paid invoice ended a Sunday).

## Recording a payment

Append one object to `%APPDATA%\WorkClock\billing.json` `payments[]`:
`{project, period_start, period_end, paid_on, hours, rate, amount, note}`.
Use the paid week's Sat..Fri range where possible. Regenerate — the matching
weeks fold into Paid automatically. The generator never writes billing.json.

## Data (read-only)

- `%APPDATA%\WorkClock\Time_Worked.json` — sessions
- `%APPDATA%\WorkClock\billing.json` — payments ledger
- `%APPDATA%\WorkClock\state.json` — per-project `rate`

## Gotchas

- Zero/negative `duration_seconds` sessions contribute 0 (harmless); clean them
  in WorkClock if they clutter notes.
- AMD is always the 3 projects bundled (ASANDRA_POC, ASANDRA_APP, SITEREVAMP).
- Tests: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -v`
```

- [ ] **Step 2: Write `CLAUDE.md`**

```markdown
# WorkClock — Claude session reference

WorkClock is an always-on-top time tracker. Data lives in
`%APPDATA%\WorkClock\` (`/mnt/c/Users/Xliminal/AppData/Roaming/WorkClock/`
from WSL): `state.json`, `Time_Worked.json`, `billing.json`.

## Billing

To post a client bill:

    ./venv/Scripts/python.exe -m billing.generate amd      # 3 AMD projects
    ./venv/Scripts/python.exe -m billing.generate gloria   # outstanding-only

Writes `C:\Users\Xliminal\<CLIENT>_billing_summary.html` for screenshot/email.
See `billing/DEVDOC.md` for the Friday-week model and how to record a payment.

| Client | Projects | Rate | Cadence |
|---|---|---|---|
| amd | ASANDRA_POC, ASANDRA_APP, SITEREVAMP | $25/hr | weekly, bill EOD Fri |
| gloria | GLORIA | $55/hr | lump sum at project end |

## Tests

    ./venv/Scripts/python.exe -m pytest tests/ -v

## App gotchas

See `README.md` "Common gotchas" — WebView2 caches aggressively (kill BOTH
python.exe and pythonw.exe, bump `?v=` on relaunch); screenshot via
`tools/capture.py`.
```

- [ ] **Step 3: Commit**

```bash
git add billing/DEVDOC.md CLAUDE.md
git commit -m "docs: billing DEVDOC + repo CLAUDE.md"
```

---

### Task 8: End-to-end verification on real data

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: all green (existing 22 + new billing tests)

- [ ] **Step 2: Generate the real AMD bill**

Run: `./venv/Scripts/python.exe -m billing.generate amd --today 2026-05-16 --out 'C:\Users\Xliminal\AMD_billing_summary.html'`
Expected stdout: `Wrote ... (outstanding 1,202.50, paid 1,101.50)`

- [ ] **Step 3: Verify the number matches the spec**

The outstanding total MUST equal **$1,202.50** (closed Weeks 4–5, hours rounded
to 2dp before × rate so rows self-check) and paid **$1,101.50**. If it differs,
STOP and reconcile against
`docs/superpowers/specs/2026-05-16-billing-summary-design.md` before continuing.

- [ ] **Step 4: Visual check**

Open `/mnt/c/Users/Xliminal/AMD_billing_summary.html` in a browser
(`cmd.exe /c start "" "C:\Users\Xliminal\AMD_billing_summary.html"`).
Confirm: week captions under both column headers, 3 project rows, the
"Week 6 in progress — not yet billed" line, totals reconcile.

- [ ] **Step 5: Generate Gloria (smoke)**

Run: `./venv/Scripts/python.exe -m billing.generate gloria --today 2026-05-16`
Expected: exit 0, Paid column absent, GLORIA outstanding shown at $55/hr.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: verified billing generator on live AMD + Gloria data"
```

---

## Self-Review

**Spec coverage:**
- Source data read-only → Task 1 (`_read_json`, no writes). ✓
- Client→project map, rates → Task 1 (`CLIENTS`, `project_rate`). ✓
- Friday week, weekend roll-forward, stub, numbering → Tasks 2–3. ✓
- Closed vs open, paid/outstanding tagging → Tasks 3–4. ✓
- HTML artifact + captions + open-week line + modes → Task 5. ✓
- CLI `generate.py` defaults → Task 6. ✓
- DEVDOC + CLAUDE.md → Task 7. ✓
- Error handling: missing billing.json (Task 1 default), unknown client
  (Task 6 rc=2), zero-duration harmless (covered by sum logic). ✓
- Testing matches spec's test list → Tasks 1–6. ✓
- Worked-example numbers ($1,202.50 / $1,101.50) → Task 8 gate. ✓

**Placeholder scan:** none — every step has full code/commands.

**Type consistency:** `Week` dataclass fields (`num,start,end,closed,by_project,
total_hours,total_amount`) used identically in Tasks 3–4; `summary()` dict keys
(`projects,paid_total,outstanding_total,outstanding_hours_total,paid_caption,
outstanding_caption,open_week,generated,client`) consumed identically in
Task 5 `render()` and Task 6 CLI. `CLIENTS`, `project_rate`, `fmt`, `_parse`,
`week_end_friday`, `paid_week_count`, `_client_paid_period` defined before use.

No gaps found.
