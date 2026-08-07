"""Turning dry-run output into the WHAT CHANGES block.

This is the other half of the promise that the model never writes a warning.
The numbers a user reads come from here, parsed out of real tool output.

If parsing fails we say so plainly. We never guess, and we never fall back
to letting the model describe the change.
"""
from __future__ import annotations

import re

# apt --simulate lines look like:
#   Inst vlc (3.0.20-1 Ubuntu:24.04/noble [amd64])
#   Remv gimp [2.10.36-1]
#   Conf vlc (3.0.20-1 ...)
_INST = re.compile(r"^Inst\s+(\S+)")
_REMV = re.compile(r"^Remv\s+(\S+)")

# Summary lines:
#   After this operation, 18.4 MB of additional disk space will be used.
#   After this operation, 241 MB disk space will be freed.
_SPACE_USED = re.compile(
    r"After this operation, ([\d.,]+ ?[kKMG]?B) of additional disk space will be used"
)
_SPACE_FREED = re.compile(
    r"After this operation, ([\d.,]+ ?[kKMG]?B) disk space will be freed"
)


def summarise(parser: str | None, output: str, *, ok: bool) -> str:
    """Dispatch to a named parser. Unknown parser → honest fallback."""
    if not ok:
        return _failed_preview(output)
    if parser == "apt_simulate":
        return _apt_simulate(output)
    if parser == "systemd_show":
        return _systemd_show(output)
    return _generic(output)


def _failed_preview(output: str) -> str:
    detail = ""
    for line in output.splitlines():
        s = line.strip()
        if s.startswith("E:"):
            detail = s[2:].strip()
            break
    if "Unable to locate package" in output:
        name = ""
        m = re.search(r"Unable to locate package (\S+)", output)
        if m:
            name = m.group(1)
        return (
            f"I couldn't find a program called {name or 'that'} in Ubuntu's "
            "catalogue.\nIt may be spelled differently — want me to search?"
        )
    return (
        "I couldn't preview this change."
        + (f"\nThe system said: {detail}" if detail else "")
    )


def _apt_simulate(output: str) -> str:
    added = [m.group(1) for line in output.splitlines() if (m := _INST.match(line.strip()))]
    removed = [m.group(1) for line in output.splitlines() if (m := _REMV.match(line.strip()))]

    lines: list[str] = []
    if added:
        lines.append(f"+ {_count(len(added), 'new program')} added")
        lines.append(f"  {_name_list(added)}")
    if removed:
        lines.append(f"- {_count(len(removed), 'program')} removed")
        lines.append(f"  {_name_list(removed)}")

    if m := _SPACE_USED.search(output):
        lines.append(f"· Uses about {m.group(1)} more disk space")
    elif m := _SPACE_FREED.search(output):
        lines.append(f"· Frees about {m.group(1)} of disk space")

    if not added and not removed:
        return "Nothing would actually change — it's already how you want it."

    if added and not removed:
        lines.append("· Nothing is removed or overwritten")

    return "\n".join(lines)


def _systemd_show(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Description="):
            return f"· Restarts: {line.split('=', 1)[1].strip()}"
    return "· Restarts this background service"


def _generic(output: str) -> str:
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    if not lines:
        return "No changes to preview."
    return "\n".join(f"· {ln[:70]}" for ln in lines[:6])


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _name_list(names: list[str], limit: int = 6) -> str:
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:limit]) + f", and {len(names) - limit} more"
