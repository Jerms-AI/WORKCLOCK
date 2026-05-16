"""CLI: python -m billing.generate <client> [--mode ...] [--out ...] [--today ...]

Examples:
  python -m billing.generate amd
  python -m billing.generate gloria --mode outstanding-only
  python -m billing.generate dashboard
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from billing import billing as B
from billing import render as R

_DEFAULT_MODE = {"amd": "full", "gloria": "outstanding-only"}


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="billing.generate")
    ap.add_argument("client")
    ap.add_argument("--mode", choices=["full", "outstanding-only"], default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--today", default=None,
                    help="YYYY-MM-DD override (default: real today)")
    args = ap.parse_args(argv)

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


if __name__ == "__main__":
    raise SystemExit(main())
