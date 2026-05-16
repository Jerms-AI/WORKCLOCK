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
