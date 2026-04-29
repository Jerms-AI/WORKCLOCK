"""Normalize project paths to Windows-readable form for storage."""
from __future__ import annotations

import re

WSL_DISTRO = "Ubuntu"


def normalize_path(input_path: str) -> str:
    """Accept Linux/WSL/Windows paths; return Windows-readable form.

    Examples:
        C:\\foo\\bar      -> C:\\foo\\bar
        C:/foo/bar        -> C:\\foo\\bar
        /mnt/c/foo/bar    -> C:\\foo\\bar
        /home/jermsai/X   -> \\\\wsl$\\Ubuntu\\home\\jermsai\\X
    """
    p = input_path.rstrip("/").rstrip("\\")

    win_drive = re.match(r"^([A-Za-z]):[/\\](.*)$", p)
    if win_drive:
        drive, rest = win_drive.groups()
        return f"{drive.upper()}:\\" + rest.replace("/", "\\")

    mnt = re.match(r"^/mnt/([a-z])(/(.*))?$", p)
    if mnt:
        drive = mnt.group(1).upper()
        rest = mnt.group(3) or ""
        return f"{drive}:\\" + rest.replace("/", "\\")

    if p.startswith("/"):
        rest = p.lstrip("/").replace("/", "\\")
        return f"\\\\wsl$\\{WSL_DISTRO}\\{rest}"

    raise ValueError(f"Cannot normalize path: {input_path!r}")
