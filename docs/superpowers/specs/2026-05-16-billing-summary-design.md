# Billing Summary Generator — Design Spec

**Date:** 2026-05-16
**Status:** Approved (design), pending implementation plan
**Owner:** Jeremy / Cyber Canvas Collective

## Problem

Client bills are currently hand-built by Claude on request (a one-off styled HTML),
screenshotted, and sent via WhatsApp; payment collected by Venmo. This works but is
not repeatable — every bill requires re-explaining the data, the layout, and the
paid/outstanding split. There is no consistent week structure, so "what is paid vs
owed" is reconstructed by hand each time and is error-prone (e.g. a runaway timer
once inflated a figure by ~27h).

## Goal (Phase 1 only)

A repeatable generator that turns existing WorkClock data into a professional,
per-client billing summary HTML that can be screenshotted and emailed. **No cloud,
no hosting, no client portal, no auth** — everything stays local. Those remain
explicitly out of scope (see Future Phases).

## Non-goals / Out of scope

- Cloud storage of billing data or summaries.
- Client login / portal / hosted devdocs / signatures / gantt charts.
- Automated email sending (user screenshots + sends manually for now).
- A scheduled job. The generator is Friday-boundary-aware so it is correct
  whenever run; a true Friday-EOD scheduled run is a deferred later add.
- Changing WorkClock's tracking behavior.

## Source data (unchanged, local)

- `%APPDATA%\WorkClock\Time_Worked.json` — per-session log
  (`project, date, start, stop, duration_seconds, note`).
- `%APPDATA%\WorkClock\billing.json` — payment ledger; one entry per received
  payment (`project, period_start, period_end, paid_on, hours, rate, amount, note`).
  This stays the source of truth for what has been **paid** (client literally sent
  the money). The generator never recomputes paid amounts — it reads them.

WSL paths: `/mnt/c/Users/Xliminal/AppData/Roaming/WorkClock/...`

## Client → project mapping

| Client | WorkClock projects | Rate | Pay cadence |
|---|---|---|---|
| `amd` | `ASANDRA_POC`, `ASANDRA_APP`, `SITEREVAMP` (always bundled) | $25/hr | weekly, billed EOD Friday |
| `gloria` | `GLORIA` | $55/hr | lump sum at project end |

(Rates read from `state.json` per project; $25 is current AMD, $55 Gloria.)

## Billing-week model

- A **billing week is the 7-day period ending Friday EOD (Saturday → Friday).**
- Work done on a weekend belongs to the week ending the **upcoming** Friday.
- A week is **CLOSED / billable** the moment its Friday has passed. The current
  in-progress week is displayed but **not billed** until its Friday closes.
- Week numbering is continuous from the first invoiced period. Weeks 1–3 correspond
  to the historical paid invoice (Apr 13 – May 3); going-forward weeks continue
  (Week 4 = May 4–8, the one-time short "transition" stub because the paid invoice
  ended Sunday May 3; Week 5 = May 9–15 Sat–Fri; etc.).
- A week is tagged **PAID** if its date range is covered by a `billing.json`
  payment entry for that client; otherwise **OUTSTANDING**. When a payment is
  received, Claude appends a `billing.json` entry and the matching weeks flip to
  paid automatically on next generation.

### Worked example (as of 2026-05-16)

| Week | Range | Status |
|---|---|---|
| 1–3 | Apr 13 – May 3 | PAID $1,101.50 ✓ |
| 4 | May 4 – May 8 (Fri) | CLOSED → billable, $524.72 |
| 5 | May 9 – May 15 (Fri) | CLOSED → billable, $677.75 |
| 6 | May 16 – May 22 (Fri) | open, in progress, not billed |

Outstanding bill (Weeks 4–5): ASANDRA_POC $144.50, ASANDRA_APP $512.00,
SITEREVAMP $546.00 → **$1,202.50 / 48.10 h**.

(Per-project hours are rounded to 2dp first, then × rate, so every displayed
row self-checks `hours × rate = amount` and the rows sum exactly to the total.
This is why the total is $1,202.50, not the raw-precision $1,202.46.)

## The artifact (HTML output)

Reuses the approved aesthetic (Amber editorial: Fraunces + Inter, parchment
`#f6f4ef`, terracotta `#c2410c`, paid-green `#5a7d54`). Single self-contained file,
no dependencies, suitable for screenshot or email attachment.

Layout = the existing per-project Paid vs Outstanding table, **with a week caption
under each column header**:

- Under **Paid (invoiced)**: `Weeks 1–3 · Apr 13 – May 3 · settled May 8 ✓`
- Under **Outstanding**: `Weeks 4–5 · May 4 – May 15`

Plus a faint line for the current open week
(`Week 6 (in progress, not yet billed): N.NN h`) so accruing time is visible
without being billed.

`--mode`:
- `full` (default, AMD) — both Paid and Outstanding columns.
- `outstanding-only` (Gloria) — drop the Paid column entirely.

## Components

1. **`billing/billing.py`** — pure logic, unit-testable, no I/O of its own beyond
   reading the two JSON files via a small loader:
   - `load_data()` → sessions + payments.
   - `billing_weeks(client, today)` → ordered list of week objects
     `{num, start, end_friday, closed, by_project{}, total_hours, total_amount,
     paid: bool}`.
   - `summary(client, today)` → per-project `{paid_hours, paid_amount,
     outstanding_hours, outstanding_amount}` + week captions + open-week figure.
   - Friday math and the paid/outstanding tagging live here.
2. **`billing/render.py`** — takes a `summary()` result + mode, returns the HTML
   string (template constant + f-string substitution). No business logic.
3. **`billing/generate.py`** — thin CLI:
   `python billing/generate.py <client> [--mode full|outstanding-only] [--out PATH]`.
   Defaults: AMD→full, Gloria→outstanding-only; default out
   `C:\Users\Xliminal\<CLIENT>_billing_summary.html`.

This isolation mirrors WorkClock's existing `state.py` / `time_worked.py` split
(pure modules unit-tested; glue thin).

## Recording a payment

When a client pays, Claude appends one entry to `billing.json` with the covered
`period_start`/`period_end` (aligned to billing-week Fridays where possible) and
the amount actually received. No other step; regeneration reflects it.

## Error handling

- Missing/empty `billing.json` → treat as zero payments (all outstanding).
- Unknown client name → exit non-zero with the valid client list.
- A `duration_seconds <= 0` session (e.g. the stray `0h00m` "df" entry) → included
  in sums (contributes 0) but the generator logs a one-line stderr warning listing
  zero/negative entries so they can be cleaned in WorkClock.
- Generator never mutates source JSON (read-only); only `generate.py` writes the
  HTML output file.

## Testing

`tests/test_billing.py` (pytest, same harness/fixtures as existing suite):
- Friday-week bucketing incl. the weekend-rolls-forward rule and the short
  transition week.
- closed vs open week classification for a given `today`.
- paid/outstanding tagging against a synthetic `billing.json`.
- per-project + total sums for a known fixture (the worked example above).
- `outstanding-only` mode omits the paid column.
Render is verified by generating and screenshotting (manual / Claude eyes).

## Documentation deliverables

- **`billing/DEVDOC.md`** — how the generator works, the week model, how to record
  a payment, how to regenerate, gotchas.
- **`CLAUDE.md`** (WorkClock repo root) — data file locations, client→project
  mapping, rates, "to post a bill: run `billing/generate.py <client>`", and the
  Friday cadence — so any future session needs no re-explanation.

## Future phases (sketched, NOT in this spec)

- **Phase 2:** A small CCC dashboard (still static/local) listing clients →
  weekly drill-down.
- **Phase 3:** Client portal — auth, per-client hosted docs, signatures, gantt.
  Separate spec/plan/cycle, only when a client actually requires it.
- **Optional later:** scheduled Friday-EOD regeneration + notification.

## Success criteria

"Post the AMD bill" / "post the Gloria bill" becomes a single command producing a
correct, professional HTML the user can screenshot and send, with paid vs
outstanding split automatically by Friday-ending billing weeks, requiring no
re-explanation in future sessions.
