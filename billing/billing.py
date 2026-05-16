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


def week_end_friday(d: date) -> date:
    """The Friday on or after d (weekday(): Mon=0 .. Fri=4 .. Sun=6)."""
    return d + timedelta(days=(4 - d.weekday()) % 7)


def paid_week_count(period_start: date, period_end: date) -> int:
    """Number of 7-day weeks the paid invoice spans (inclusive, ceil)."""
    days = (period_end - period_start).days + 1
    return (days + 6) // 7


@dataclass
class Week:
    num: int
    start: date
    end: date  # a Friday
    closed: bool  # True when the week's Friday (end) is before today
    by_project: dict[str, float] = field(default_factory=dict)  # hours
    total_hours: float = 0.0
    total_amount: float = 0.0


def _parse(ds: str) -> date:
    y, m, d = (int(x) for x in ds.split("-"))
    return date(y, m, d)


def _client_paid_period(client: str, payments: list[dict]):
    """(period_start, period_end, paid_on) across the client's projects, or None.

    Assumes all of a client's projects share the same paid period and takes
    min/max across records — a future invoice covering only some projects with
    a later period_end would skip the others' work.
    """
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
    rates = {n: project_rate(n) for n in names}
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
        total_amount = sum(h * rates.get(p, 0) for p, h in by_project.items())
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
    outstanding_total = round(
        sum(p["outstanding_amount"] for p in projects.values()), 2)
    outstanding_hours_total = round(
        sum(p["outstanding_hours"] for p in projects.values()), 2)

    if period:
        ps, pe, po = period
        pwc = paid_week_count(ps, pe)
        wk = "Week 1" if pwc == 1 else f"Weeks 1–{pwc}"
        paid_caption = (f"{wk} · {fmt(ps)} – {fmt(pe)} "
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
        "generated": f"{_MON[today.month]} {today.day}, {today.year}",
    }
