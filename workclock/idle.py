"""Windows idle-time detection via GetLastInputInfo."""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_idle_seconds() -> int:
    """Seconds since last keyboard or mouse input on Windows.

    Returns 0 on non-Windows platforms or if the call fails.
    """
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0
        millis_now = ctypes.windll.kernel32.GetTickCount()
        return (millis_now - info.dwTime) // 1000
    except (OSError, AttributeError):
        return 0
