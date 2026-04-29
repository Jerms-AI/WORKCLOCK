"""Screenshot the WorkClock window. Used by Claude to self-verify UI state.

Usage: python tools/capture.py [output_path]
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
from pathlib import Path

from PIL import ImageGrab

WINDOW_TITLE = "WorkClock"


def find_hwnd() -> int:
    matches: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _lparam):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length)
        if WINDOW_TITLE == buf.value:
            matches.append(hwnd)
        return True

    ctypes.windll.user32.EnumWindows(cb, 0)
    return matches[0] if matches else 0


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("workclock.png")
    hwnd = find_hwnd()
    if not hwnd:
        print("WorkClock window not found", file=sys.stderr)
        sys.exit(1)
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    img = ImageGrab.grab(
        bbox=(rect.left, rect.top, rect.right, rect.bottom),
        all_screens=True,
    )
    img.save(out)
    print(f"saved {out} {rect.right - rect.left}x{rect.bottom - rect.top}")


if __name__ == "__main__":
    main()
