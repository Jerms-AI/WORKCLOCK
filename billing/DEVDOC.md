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
- `_client_paid_period` assumes all of a client's projects share one paid
  period (min/max across records). If a future invoice covers only some
  projects with a later `period_end`, the others' work in that span would be
  wrongly suppressed — record payments per shared period.
