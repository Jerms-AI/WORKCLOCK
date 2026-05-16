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
    out = args.out or f"C:\\Users\\Xliminal\\{client.upper()}_billing_summary.html"

    s = B.summary(client, today=today)
    html = R.render(s, client, mode=mode)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out}  (outstanding {s['outstanding_total']:,.2f}, "
          f"paid {s['paid_total']:,.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
