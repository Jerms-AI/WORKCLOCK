# CCC Dashboard — Design Spec

**Date:** 2026-05-16
**Status:** Approved (design), pending implementation plan
**Owner:** Jeremy / Cyber Canvas Collective
**Builds on:** `2026-05-16-billing-summary-design.md` (Phase 1, shipped)

## Problem

The billing generator produces one HTML per client on demand, but there is no
single at-a-glance view of all active clients and what each owes. Phase 2 of the
original decomposition: a small personal ops dashboard.

## Goal (Phase 2 only)

A static, local `dashboard.html` listing every client as a card with a live
snapshot (outstanding headline figure, paid-to-date, hours, as-of date) that
links to that client's full billing summary HTML. One command regenerates the
dashboard **and** every client bill so they never drift apart.

## Non-goals / out of scope

- Cloud hosting, auth, client portal (Phase 3, separate spec).
- Per-week drill-down on the dashboard itself — that detail already lives in
  each client's billing summary; the dashboard only links to it.
- Any change to the Friday-week billing logic or `billing.py` math.
- Email/automation/scheduling.

## Clients shown

Driven by `billing.CLIENTS` (single source of truth — adding a future client
there makes it appear on the dashboard automatically):

| Card | Display name | Bundled projects (subtitle) | Mode of its bill |
|---|---|---|---|
| `gloria` | Gloria | GLORIA | outstanding-only |
| `amd` | AMD International | ASANDRA_POC · ASANDRA_APP · SITEREVAMP | full |

## The artifact

`C:\Users\Xliminal\dashboard.html` — single self-contained file, Amber
editorial aesthetic identical to the bills (Fraunces + Inter, parchment
`#f6f4ef`, terracotta `#c2410c`, paid-green `#5a7d54`). Suitable for local
viewing / screenshot.

Layout: a header (`Cyber Canvas Collective` eyebrow, "Dashboard" title, "As of
<date>"), then one card per client:

- **Client display name** (Fraunces, links to the bill).
- **Subtitle**: the bundled project names.
- **Headline**: outstanding amount, large, terracotta (e.g. `$1,202.50`), with
  outstanding hours beneath (`48.10 h · Weeks 4–5`).
- **Secondary**: paid-to-date in green with a check (`$1,101.50 paid ✓`); for a
  client with no payments (Gloria) show `— not yet invoiced` instead.
- The whole card is an `<a href="<CLIENT>_billing_summary.html">` (relative —
  same folder as the bills, so links work on the local filesystem).
- A footer note: figures reflect closed Friday-ending billing weeks.

A client whose outstanding total is `0` still renders (shows `$0.00`).

## Invocation

Extend the existing CLI with a `dashboard` pseudo-target:

    ./venv/Scripts/python.exe -m billing.generate dashboard

This:
1. For every client in `billing.CLIENTS`: compute `summary()`, render its bill
   in its default mode, write `C:\Users\Xliminal\<CLIENT>_billing_summary.html`
   (exact same output as running each client individually — no logic fork).
2. Render the dashboard from those same summaries and write
   `C:\Users\Xliminal\dashboard.html`.
3. Print one line per file written, plus the existing zero/negative-duration
   stderr warnings (now scanned across all clients).

`--today` and `--out` still apply (`--out` overrides the dashboard path only;
per-client bills keep their standard path so the relative links resolve).
Existing single-client invocations (`... generate amd`) are unchanged.

## Components

- **`billing/billing.py`** — unchanged logic. (Already exposes `CLIENTS`,
  `summary`, `_DEFAULT_MODE` lives in generate.) No new math.
- **`billing/render.py`** — add `render_dashboard(summaries, today) -> str`
  where `summaries` is an ordered `dict[client -> summary()-dict]`. Pure
  presentation, mirrors existing `render()`; reuses the shared `_CSS` and
  `_money`/`_TITLES` helpers (extract `_CSS`/`_money`/`_TITLES` are already
  module-level — reuse as-is, do not duplicate).
- **`billing/generate.py`** — add handling for `client == "dashboard"`:
  iterate `CLIENTS`, reuse the existing per-client summary+render+write path
  (refactor that path into a small local helper `_write_bill(client, today)`
  so the single-client and dashboard paths share one code path — no
  duplicated logic), then call `render_dashboard` and write `dashboard.html`.
  The zero/negative scan runs per client inside the shared helper.

This keeps the existing module boundaries: `billing`=logic, `render`=HTML,
`generate`=CLI orchestration.

## Error handling

- Unknown client (non-`dashboard`, not in `CLIENTS`) → unchanged (exit 2).
- `dashboard` with an empty `CLIENTS` → write a dashboard with a "no clients"
  message, exit 0 (defensive; cannot happen with current constant).
- Source JSON still read-only; only `generate.py` writes HTML files.
- Per-client zero/negative-duration warnings printed to stderr (existing
  behavior, now also covered when generating via `dashboard`).

## Testing

`tests/test_billing.py` additions (pytest, existing `tmp_appdata` fixture):
- `render_dashboard` output contains both client display names, both
  `<CLIENT>_billing_summary.html` relative hrefs, each client's outstanding
  `_money` figure, and the AMD bundled-project subtitle.
- Gloria card shows the "not yet invoiced" treatment (no paid figure) while
  AMD shows the paid-to-date figure.
- `generate.main(["dashboard", ...])` writes 3 files (2 bills + dashboard) into
  a tmp dir and returns 0; the dashboard references the bill filenames.
- A client with `$0.00` outstanding still renders a card (no crash).

## Docs

- Update `billing/DEVDOC.md`: add the `dashboard` command and what it writes.
- Update repo `CLAUDE.md`: "to see everything: `... -m billing.generate
  dashboard` → `C:\Users\Xliminal\dashboard.html`".

## Success criteria

`./venv/Scripts/python.exe -m billing.generate dashboard` produces a single
Amber-styled `dashboard.html` with a Gloria card and an AMD card, each showing
the correct live outstanding/paid figures and linking to a freshly regenerated
billing summary that opens correctly from the dashboard.
