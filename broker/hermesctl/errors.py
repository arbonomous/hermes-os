"""Turning system error output into something a beginner can act on.

docs/03-ux-model.md: "Zero cryptic error messages." Passing apt's stderr
straight through breaks that promise, so the errors a beginner will
actually hit get a translation and a next step.

Anything unrecognised is shown verbatim — an unfamiliar real error beats an
invented friendly one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Explanation:
    what: str            # what went wrong, in plain words
    why: str = ""        # the likely cause
    next_step: str = ""  # what the user can do

    def render(self) -> str:
        parts = [self.what]
        if self.why:
            parts.append(self.why)
        if self.next_step:
            parts.append(self.next_step)
        return "\n\n".join(parts)


# Ordered: first match wins, so put specific patterns above general ones.
_RULES: list[tuple[re.Pattern, Explanation]] = [
    (re.compile(r"Could not get lock .*dpkg", re.I), Explanation(
        what="Something else is already installing software right now.",
        why="Ubuntu only lets one thing install at a time, so I have to wait "
            "my turn. This usually clears by itself within a minute or two.",
        next_step="Try again shortly and it should go through.",
    )),
    (re.compile(r"Unable to locate package (\S+)", re.I), Explanation(
        what="I couldn't find that program in Ubuntu's catalogue.",
        why="It might be spelled differently, or go by another name.",
        next_step='Tell me what you want it to do and I\'ll look for '
                  'something that fits.',
    )),
    (re.compile(r"Temporary failure resolving|Could not resolve host", re.I), Explanation(
        what="I can't reach the internet at the moment.",
        why="The download server couldn't be found, which usually means the "
            "connection has dropped.",
        next_step='Say "check my internet" and I\'ll take a look.',
    )),
    (re.compile(r"No space left on device", re.I), Explanation(
        what="The disk is full.",
        why="There isn't enough room left to install anything new.",
        next_step='Say "what\'s using my disk space?" and I\'ll show you the '
                  'biggest things.',
    )),
    (re.compile(r"dpkg was interrupted", re.I), Explanation(
        what="An earlier install was cut off partway through.",
        why="Ubuntu needs to tidy that up before it can install anything new.",
        next_step='Say "fix my package manager" and I\'ll repair it for you.',
    )),
    (re.compile(r"Permission denied|EACCES", re.I), Explanation(
        what="I wasn't allowed to do that.",
        why="The file or folder belongs to someone else on this computer.",
        next_step="Type !shell if you want to take a look yourself.",
    )),
    (re.compile(r"Unit (\S+) not found", re.I), Explanation(
        what="That background service isn't installed on this computer.",
        why="Nothing is broken — it simply isn't here.",
        next_step='Say "what services are running?" to see what is.',
    )),
    (re.compile(r"Held broken packages|unmet dependencies", re.I), Explanation(
        what="This program needs other programs that clash with what's "
             "already installed.",
        why="Installing it would break something you already have, so Ubuntu "
            "stopped.",
        next_step="I'd leave this one alone unless you know you need it.",
    )),
]


def explain(output: str) -> Explanation | None:
    """Find a friendly explanation, or None if we don't recognise it."""
    for pattern, expl in _RULES:
        if pattern.search(output):
            return expl
    return None


def friendly_failure(summary: str, output: str, *, snapshot: bool) -> str:
    """The full failure message shown to the user."""
    known = explain(output)

    if known:
        parts = [known.what]
        if known.why:
            parts.append(known.why)
    else:
        parts = [f"That didn't work — {summary} failed."]
        raw = _first_useful_line(output)
        if raw:
            # Unrecognised: show it verbatim rather than invent a meaning.
            parts.append(f"The system said:\n  {raw}")

    if snapshot:
        parts.append(
            'Nothing is broken — I made a restore point first, so your '
            'computer is exactly as it was.'
        )

    if known and known.next_step:
        parts.append(known.next_step)
    else:
        parts.append("Want me to try something else?")

    return "\n\n".join(parts)


_NOISE = (
    "Reading package lists", "Building dependency tree",
    "Reading state information", "WARNING:", "debconf:",
    "Preconfiguring packages",
)


def _first_useful_line(output: str) -> str:
    """The one line a human would want. Prefer an explicit error line."""
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    for line in lines:
        if line.startswith(("E:", "Error:", "error:")):
            return line.split(":", 1)[1].strip()[:200]
    for line in lines:
        if not line.startswith(_NOISE):
            return line[:200]
    return ""
