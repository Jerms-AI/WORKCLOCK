"""hours.md per-project log: formatters and append logic."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def format_duration(seconds: int) -> str:
    """Format a duration as 'Xh Ym' or 'Ym' (seconds truncated)."""
    total_minutes = seconds // 60
    hours, minutes = divmod(total_minutes, 60)
    if hours == 0:
        return f"{minutes}m"
    return f"{hours}h {minutes}m"


def format_time(dt: datetime) -> str:
    """Format a datetime as 'HH:MM' (24-hour, local time assumed)."""
    return dt.strftime("%H:%M")


def append_session(
    project_dir: Path | str,
    display_name: str,
    start: datetime,
    stop: datetime,
    note: str | None,
) -> None:
    """Append a session bullet to hours.md at project_dir.

    File created with `# Hours — {display_name}` header if absent.
    Session is filed under the START date (handles midnight-crossing).
    Day section is created (prepended) if it doesn't exist.
    """
    project_dir = Path(project_dir)
    hours_file = project_dir / "hours.md"

    duration_seconds = int((stop - start).total_seconds())
    bullet = f"- {format_time(start)}–{format_time(stop)} ({format_duration(duration_seconds)})"
    if note:
        bullet += f" — {note}"
    day_header = f"## {start.strftime('%Y-%m-%d')}"

    if not hours_file.exists():
        content = f"# Hours — {display_name}\n\n{day_header}\n{bullet}\n"
        hours_file.write_text(content, encoding="utf-8")
        return

    text = hours_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)

    day_idx = None
    for i, line in enumerate(lines):
        if line.strip() == day_header:
            day_idx = i
            break

    if day_idx is not None:
        insert_at = len(lines)
        for j in range(day_idx + 1, len(lines)):
            if lines[j].startswith("## "):
                insert_at = j
                break
        while insert_at > day_idx + 1 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        lines.insert(insert_at, bullet)
    else:
        first_day_idx = None
        for i, line in enumerate(lines):
            if line.startswith("## "):
                first_day_idx = i
                break
        new_section = [day_header, bullet, ""]
        if first_day_idx is not None:
            for offset, new_line in enumerate(new_section):
                lines.insert(first_day_idx + offset, new_line)
        else:
            if lines and lines[-1].strip() != "":
                lines.append("")
            lines.extend(new_section[:-1])

    hours_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
