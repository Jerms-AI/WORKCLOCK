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
      <div class="date">As of {s["generated"]}</div>
    </header>
    <table>
      <thead><tr><th>Project</th>{head_paid}{head_out}</tr></thead>
      <tbody>{rows}{total_row}</tbody>
    </table>
    {openwk}
    <footer>
      Paid amounts reflect received payments. Outstanding reflects closed
      Friday-ending billing weeks not yet invoiced.
    </footer>
  </div>
</body>
</html>
"""


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
