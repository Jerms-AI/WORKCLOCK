# CCC Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A static local `dashboard.html` with one card per client (live outstanding/paid snapshot, links to that client's billing summary), regenerated together with all client bills by one command.

**Architecture:** Reuse `billing.summary()` (no new math). Add a pure `render_dashboard()` to `render.py`. Refactor `generate.py`'s per-client write path into a shared `_write_bill()` helper and add a `dashboard` pseudo-target that calls it for every client then renders the dashboard. Module boundaries unchanged: `billing`=logic, `render`=HTML, `generate`=CLI.

**Tech Stack:** Python 3.13 stdlib only. pytest with existing `tmp_appdata` fixture.

---

## Reference

Spec: `docs/superpowers/specs/2026-05-16-dashboard-design.md`. The billing
generator (Phase 1) is shipped: `billing/billing.py` (`CLIENTS`, `summary`),
`billing/render.py` (`render`, module-level `_CSS`, `_TITLES`, `_money`),
`billing/generate.py` (`main`, `_DEFAULT_MODE`). Test runner:
`./venv/Scripts/python.exe -m pytest`. Commit to `main`, do NOT push.

`summary(client, today)` returns a dict with keys: `client`, `projects`
(ordered dict project-name -> {paid_hours,paid_amount,outstanding_hours,
outstanding_amount}), `paid_total`, `outstanding_total`,
`outstanding_hours_total`, `paid_caption`, `outstanding_caption`,
`open_week`, `generated` (e.g. `"May 16, 2026"`).

## File Structure

- Modify `billing/render.py` — append card CSS to `_CSS`; add
  `render_dashboard(summaries, generated)`.
- Modify `billing/generate.py` — extract `_write_bill(client, today)`; add
  `dashboard` target in `main`.
- Modify `tests/test_billing.py` — append dashboard tests.
- Modify `billing/DEVDOC.md`, `CLAUDE.md` — document the command.

---

### Task 1: `render_dashboard()` + card CSS

**Files:**
- Modify: `billing/render.py`
- Test: `tests/test_billing.py`

- [ ] **Step 1: Append the failing test to the end of `tests/test_billing.py`**

```python
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
    # AMD card: title, bundled-projects subtitle, outstanding headline, paid line
    assert "AMD International" in html
    assert "ASANDRA_POC · ASANDRA_APP · SITEREVAMP" in html
    assert "$112.50" in html
    assert "$1,101.50 paid ✓" in html
    assert 'href="AMD_billing_summary.html"' in html
    # Gloria card: no payments -> "not yet invoiced", own link
    assert "Gloria" in html
    assert "not yet invoiced" in html
    assert 'href="GLORIA_billing_summary.html"' in html
```

- [ ] **Step 2: Run, expect FAIL**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k render_dashboard -v`
Expected: FAIL — `AttributeError: module 'billing.render' has no attribute 'render_dashboard'`

- [ ] **Step 3: In `billing/render.py`, append card styles to the `_CSS` string**

Find the end of the `_CSS` triple-quoted string (the line `footer{margin-top:36px;color:#6b6358;font-size:13px;line-height:1.6}` immediately followed by the closing `"""`). Insert these rules immediately BEFORE the closing `"""` (i.e. after the `footer{...}` line, still inside the string):

```css
a.card{display:block;text-decoration:none;color:inherit;
border:1px solid #ddd6c9;border-radius:10px;padding:24px 26px;margin-bottom:18px;
transition:border-color .15s}
a.card:hover{border-color:#c2410c}
.card .cname{font-family:'Fraunces',Georgia,serif;font-size:24px;
font-weight:600;color:#1f1c18}
.card .csub{font-size:12px;color:#6b6358;letter-spacing:.04em;margin-top:4px}
.card .cout{font-size:34px;font-weight:700;color:#c2410c;
font-variant-numeric:tabular-nums;margin-top:16px}
.card .chrs{font-size:13px;color:#6b6358;margin-top:4px}
.card .cpaid{font-size:13px;margin-top:10px;color:#5a7d54;font-weight:600}
.card .cpaid.none{color:#6b6358;font-weight:400;font-style:italic}
```

- [ ] **Step 4: In `billing/render.py`, add `render_dashboard` at the end of the file**

```python
def render_dashboard(summaries: dict, generated: str) -> str:
    """Render an ordered {client: summary()-dict} mapping to a dashboard HTML.
    Pure presentation; reuses _CSS / _TITLES / _money."""
    cards = ""
    if not summaries:
        cards = '<p class="csub">No clients configured.</p>'
    for client, s in summaries.items():
        title = _TITLES.get(client, client.upper())
        subtitle = " · ".join(s["projects"].keys())
        href = f"{client.upper()}_billing_summary.html"
        if s["paid_total"]:
            paid = (f'<div class="cpaid">{_money(s["paid_total"])} paid '
                    f'✓</div>')
        else:
            paid = '<div class="cpaid none">— not yet invoiced</div>'
        cards += (
            f'<a class="card" href="{href}">'
            f'<div class="cname">{title}</div>'
            f'<div class="csub">{subtitle}</div>'
            f'<div class="cout">{_money(s["outstanding_total"])}</div>'
            f'<div class="chrs">{s["outstanding_hours_total"]:.2f} h'
            f' · {s["outstanding_caption"]}</div>'
            f'{paid}</a>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Cyber Canvas Collective — Dashboard</title>
<style>{_CSS}</style>
</head>
<body>
  <div class="sheet">
    <header>
      <div class="eyebrow">Cyber Canvas Collective</div>
      <h1>Dashboard</h1>
      <div class="date">As of {generated}</div>
    </header>
    {cards}
    <footer>
      Outstanding reflects closed Friday-ending billing weeks not yet
      invoiced. Click a client for the full billing summary.
    </footer>
  </div>
</body>
</html>
"""
```

- [ ] **Step 5: Run, expect PASS; then full suite**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k render_dashboard -v` (expect 1 passed)
Run: `./venv/Scripts/python.exe -m pytest tests/ -v` (expect no regressions; 36 passed)

- [ ] **Step 6: Commit**

```bash
git add billing/render.py tests/test_billing.py
git commit -m "feat: render_dashboard() + card styles"
```

---

### Task 2: Refactor generate.py per-client path into `_write_bill()`

**Files:**
- Modify: `billing/generate.py`
- Test: `tests/test_billing.py` (no new test; existing generate tests must stay green — this is a behavior-preserving refactor)

Current `billing/generate.py` `main()` body (after arg parsing + the
`if client not in B.CLIENTS` guard + `today` computation) builds `mode`,
`out`, the zero-duration `bad` scan/warning, then `summary`, `render`, file
write, and the `Wrote ...` print. Extract everything from `mode = ...`
through the print into a helper, returning the summary.

- [ ] **Step 1: Replace the tail of `main()` with a shared helper**

In `billing/generate.py`, add this helper ABOVE `def main(`:

```python
def _write_bill(client: str, today, out: str | None = None) -> dict:
    """Compute a client's summary, render its bill, write the HTML, print a
    line, emit zero/negative-duration warnings. Returns the summary dict."""
    mode = _DEFAULT_MODE.get(client, "full")
    out = out or f"C:\\Users\\Xliminal\\{client.upper()}_billing_summary.html"

    bad = [
        f'{x.get("project")} {x.get("date")} ({x.get("duration_seconds")}s)'
        for x in B.load_sessions()
        if x.get("project") in B.CLIENTS[client]
        and x.get("duration_seconds", 0) <= 0
    ]
    if bad:
        print(f"WARNING: {len(bad)} zero/negative-duration session(s) for "
              f"{client} (contribute $0; clean in WorkClock): "
              + "; ".join(bad), file=sys.stderr)

    s = B.summary(client, today=today)
    html = R.render(s, client, mode=mode)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out}  (outstanding {s['outstanding_total']:,.2f}, "
          f"paid {s['paid_total']:,.2f})")
    return s
```

Then change the body of `main()` so that, after the `today` computation and
the unknown-client guard, the single-client path simply calls the helper.
The relevant region of `main()` (from the `mode = ...` line to the end of the
function, but NOT the `return 0`) is replaced. Final `main()` reads:

```python
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

    _write_bill(client, today, out=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

NOTE: the `--mode` arg is now unused by the single-client path (the helper uses
`_DEFAULT_MODE`). This matches current real behavior — every existing call
relies on the default mode and no test passes `--mode`. Keep the `--mode`
argument defined (harmless, documented) but do not wire it through; a follow-up
could thread it into `_write_bill` if ever needed. Do NOT delete it.

- [ ] **Step 2: Run the existing generate tests, expect unchanged PASS**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k generate -v`
Expected: PASS — `test_generate_writes_html`, `test_generate_unknown_client_errors`, `test_generate_warns_on_zero_duration` all green (3 passed).

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: no regressions (36 passed).

- [ ] **Step 3: Commit**

```bash
git add billing/generate.py
git commit -m "refactor: extract _write_bill() shared per-client path"
```

---

### Task 3: `dashboard` target in generate.py

**Files:**
- Modify: `billing/generate.py`
- Test: `tests/test_billing.py`

- [ ] **Step 1: Append the failing test to the end of `tests/test_billing.py`**

```python
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
```

This test passes a directory-relative `--out` for the dashboard; the
per-client bills must be written into the SAME directory as the dashboard so
the relative `href`s resolve. Implement accordingly (derive the bills'
directory from the dashboard `--out` when provided, else the default
`C:\Users\Xliminal\` folder).

- [ ] **Step 2: Run, expect FAIL**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k generate_dashboard -v`
Expected: FAIL — `dashboard` is not in `B.CLIENTS` so `main` currently returns 2 (assertion `rc == 0` fails).

- [ ] **Step 3: Add the `dashboard` branch to `main()`**

Add `import os` to the imports at the top of `billing/generate.py` (alongside
`import argparse`, `import sys`). Add `from billing import render as R` is
already imported; `_write_bill` exists from Task 2. Modify `main()` so the
unknown-client guard allows `"dashboard"`, and add the dashboard branch
BEFORE the single-client call:

Replace this block in `main()`:

```python
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

    _write_bill(client, today, out=args.out)
    return 0
```

with:

```python
    client = args.client.lower()
    if client != "dashboard" and client not in B.CLIENTS:
        print(f"Unknown client {client!r}. Valid: "
              f"{', '.join(B.CLIENTS)}, dashboard", file=sys.stderr)
        return 2

    if args.today:
        y, m, d = (int(x) for x in args.today.split("-"))
        today = date(y, m, d)
    else:
        today = date.today()

    if client == "dashboard":
        dash_out = args.out or "C:\\Users\\Xliminal\\dashboard.html"
        bills_dir = os.path.dirname(dash_out)
        summaries: dict = {}
        for c in B.CLIENTS:
            bill_out = os.path.join(bills_dir,
                                    f"{c.upper()}_billing_summary.html")
            summaries[c] = _write_bill(c, today, out=bill_out)
        generated = next(iter(summaries.values()))["generated"] \
            if summaries else ""
        html = R.render_dashboard(summaries, generated)
        with open(dash_out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Wrote {dash_out}  ({len(summaries)} client(s))")
        return 0

    _write_bill(client, today, out=args.out)
    return 0
```

Update the module docstring at the top of `billing/generate.py` to add a
`dashboard` example line under the existing examples:

```
  python -m billing.generate dashboard
```

- [ ] **Step 4: Run, expect PASS; then full suite**

Run: `./venv/Scripts/python.exe -m pytest tests/test_billing.py -k generate_dashboard -v` (expect 1 passed)
Run: `./venv/Scripts/python.exe -m pytest tests/ -v` (expect 37 passed, no regressions)

- [ ] **Step 5: Commit**

```bash
git add billing/generate.py tests/test_billing.py
git commit -m "feat: dashboard target regenerates bills + dashboard.html"
```

---

### Task 4: Docs + end-to-end Playwright QA

**Files:**
- Modify: `billing/DEVDOC.md`, `CLAUDE.md`
- Verification only otherwise.

- [ ] **Step 1: Update `billing/DEVDOC.md`**

Under the `## Run` section, after the two existing run lines, add:

```markdown

Whole dashboard (regenerates every client bill AND `dashboard.html`):

    ./venv/Scripts/python.exe -m billing.generate dashboard

Writes `C:\Users\Xliminal\dashboard.html` plus each
`C:\Users\Xliminal\<CLIENT>_billing_summary.html`; the dashboard links to the
bills by relative filename (open the dashboard locally and the links work).
```

- [ ] **Step 2: Update `CLAUDE.md`**

In the `## Billing` section, after the existing `gloria` run line, add:

```markdown
    ./venv/Scripts/python.exe -m billing.generate dashboard  # all + dashboard.html
```

- [ ] **Step 3: Commit docs**

```bash
git add billing/DEVDOC.md CLAUDE.md
git commit -m "docs: document dashboard command"
```

- [ ] **Step 4: Full suite + live generation**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v` (expect all green)
Run: `./venv/Scripts/python.exe -m billing.generate dashboard --today 2026-05-16`
Expected stdout: three `Wrote ...` lines (AMD bill, GLORIA bill, dashboard) —
AMD outstanding `1,202.50`, paid `1,101.50`.

- [ ] **Step 5: Playwright QA**

Create `/tmp/qa_dash.py`:

```python
from playwright.sync_api import sync_playwright
import pathlib
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 760, "height": 900},
                    device_scale_factor=2)
    pg.goto(pathlib.Path("/mnt/c/Users/Xliminal/dashboard.html").as_uri())
    pg.wait_for_timeout(300)
    pg.screenshot(path="/tmp/qa_dash.png", full_page=True)
    # click the AMD card, confirm it navigates to the AMD bill
    pg.click("text=AMD International")
    pg.wait_for_timeout(300)
    print("after click url:", pg.url)
    pg.screenshot(path="/tmp/qa_dash_amd.png", full_page=True)
    b.close()
```

Run: `python3 /tmp/qa_dash.py`
Then `Read` `/tmp/qa_dash.png` and `/tmp/qa_dash_amd.png`. Confirm visually:
two cards (Gloria, AMD International), AMD shows `$1,202.50` outstanding +
`$1,101.50 paid ✓`, Gloria shows its outstanding + "not yet invoiced",
Amber styling, and the AMD card click navigates to `AMD_billing_summary.html`
(the printed `after click url` ends with `AMD_billing_summary.html`).

- [ ] **Step 6: Final commit (if QA produced no code changes, skip)**

If QA surfaced fixes, implement, re-run suite, and:

```bash
git add -A
git commit -m "fix: dashboard QA follow-ups"
```

---

## Self-Review

**Spec coverage:**
- Static local `dashboard.html`, Amber aesthetic → Task 1 (`render_dashboard`,
  reuses `_CSS`). ✓
- One card per client from `billing.CLIENTS`, outstanding headline, paid
  secondary / "not yet invoiced", bundled-projects subtitle, card links to
  bill via relative href → Task 1. ✓
- One command regenerates dashboard + every client bill, shared per-client
  path (no logic fork) → Tasks 2 (`_write_bill`) + 3 (dashboard branch). ✓
- `--today`/`--out` apply; `--out` overrides dashboard path; bills stay
  co-located so links resolve → Task 3 (`bills_dir` from `dash_out`). ✓
- Existing single-client invocations unchanged → Task 2 (behavior-preserving;
  existing generate tests stay green). ✓
- `$0` outstanding still renders; empty `CLIENTS` → "no clients" → Task 1
  (`if not summaries`) + Task 1 card loop (no zero-suppression). ✓
- Read-only source; only `generate.py` writes → Tasks 2-3 (helper writes
  only output HTML). ✓
- Tests: dashboard cards/links/figures, gloria-no-pay treatment, 3-file
  generation → Tasks 1 & 3. ✓
- Docs (DEVDOC + CLAUDE.md) → Task 4. ✓

**Placeholder scan:** none — every step has full code/commands.

**Type consistency:** `render_dashboard(summaries: dict, generated: str)` is
defined in Task 1 and called identically in Task 3. `_write_bill(client,
today, out=None) -> dict` defined in Task 2, called with `out=` in Tasks 2 & 3.
`summary` dict keys used in Task 1 (`projects`, `paid_total`,
`outstanding_total`, `outstanding_hours_total`, `outstanding_caption`,
`generated`) match the Phase-1 `summary()` contract documented in the
Reference section. `B.CLIENTS`, `_DEFAULT_MODE`, `R` import all pre-exist.

No gaps found.
