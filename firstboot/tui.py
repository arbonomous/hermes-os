#!/usr/bin/env python3
"""firstboot/tui.py — a real terminal UI for the first-boot wizard.

Renders every screen from wizard.SCREENS and accepts keyboard navigation that
maps 1:1 onto the headless Wizard state machine. This is the actual thing a
person sees at first boot — not the browser preview. It is a thin renderer:
all answers land in the same Wizard object that emits plan(), so what you
click is what the OS runs.

Keys
----
  ↑/↓ (or k/j)   move selection on choice screens
  Enter          confirm / advance (accepts safe default on info screens)
  letters        type on text/password screens
  Backspace      delete a char
  K              open keyboard-layout picker (language screen)
  ?              toggle help (brain screen)
  T              drop to a plain terminal and exit (hello screen escape)
  Esc            skip a progress/download screen, or back out of a sub-picker

The TUI itself does no disk writes and no network. It produces a Wizard with
answers; firstbootd/converge turns that into real actions behind approval cards.
"""
from __future__ import annotations

import sys
import termios
import tty
from typing import Optional

from wizard import Wizard


# Box drawing + a calm palette. Falls back to plain text if no color.
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YEL = "\033[33m"
RED = "\033[31m"
GREY = "\033[90m"
USE_COLOR = sys.stdout.isatty()


def c(code: str, s: str) -> str:
    return f"{code}{s}{RESET}" if USE_COLOR else s


BOX_W = 64  # inner width


def _box_top() -> str:
    return c(GREY, "╭" + "─" * BOX_W + "╮")


def _box_bot() -> str:
    return c(GREY, "╰" + "─" * BOX_W + "╯")


def _box_line(s: str) -> str:
    s = (s or "")
    if len(s) > BOX_W:
        s = s[:BOX_W - 1] + "…"
    return c(GREY, "│") + s + " " * (BOX_W - len(s)) + c(GREY, "│")


def _box_gap() -> str:
    return c(GREY, "│") + " " * BOX_W + c(GREY, "│")


def render(w: Wizard, picker: Optional[list] = None, help_on: bool = False) -> str:
    scr = w.screen
    lines = [_box_top()]
    title = scr.get("title")
    if title:
        lines.append(_box_line(c(BOLD + CYAN, "  " + title)))
        lines.append(_box_gap())
    for b in scr.get("body", []):
        lines.append(_box_line("  " + b))
    lines.append(_box_gap())

    kind = scr["kind"]
    if kind == "choice":
        for i, o in enumerate(scr["options"]):
            marker = c(GREEN, "▸ ") if i == w.selection else "  "
            label = o["label"]
            suffix = ""
            if o.get("default"):
                suffix = c(DIM, "   [default]")
            line = f"  {marker}{label}{suffix}"
            if o.get("detail"):
                line += c(DIM, "   " + o["detail"])
            lines.append(_box_line(line))
        lines.append(_box_gap())
    elif kind in ("text", "password"):
        label = scr.get("input_label", "")
        if label:
            lines.append(_box_line(c(DIM, "  " + label)))
        shown = "*" * len(w.typed) if kind == "password" else w.typed
        caret = c(CYAN, "▌")
        lines.append(_box_line("  > " + shown + caret))
    elif kind == "progress":
        # static progress illustration; the live run would animate
        lines.append(_box_gap())

    # help overlay (brain)
    if help_on and scr.get("help"):
        lines.append(_box_gap())
        for hl in scr["help"].split("\n"):
            lines.append(_box_line(c(DIM, "  " + hl)))

    # picker overlay
    if picker is not None:
        lines.append(_box_gap())
        lines.append(_box_line(c(BOLD, "  Keyboard layout:")))
        for i, k in enumerate(picker):
            marker = c(GREEN, "▸ ") if i == w.selection else "  "
            lines.append(_box_line(f"  {marker}{k}"))

    # error
    err = w.answers.get("_error")
    if err:
        lines.append(_box_gap())
        lines.append(_box_line(c(RED, "  ! " + err)))

    lines.append(_box_bot())
    lines.append(c(DIM, "  " + scr.get("footer", "Enter to continue")))
    return "\n".join(lines)


KEYBOARD_LAYOUTS = [
    "US QWERTY", "US International", "UK QWERTY", "German QWERTZ",
    "French AZERTY", "Spanish", "Italian", "Japanese", "Dvorak",
]


def run() -> Wizard:
    """Drive the wizard with real keypresses until done or terminal-escape."""
    w = Wizard()
    picker: Optional[list] = None
    help_on = False
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while not w.done:
            # terminal escape (only from info screens with an escape option)
            if w.went_terminal:
                break
            scr = w.screen
            if picker is None and scr["kind"] == "choice" and help_on and not scr.get("help"):
                help_on = False
            sys.stdout.write("\033[2J\033[H")  # clear + home
            sys.stdout.write(render(w, picker, help_on) + "\n")
            sys.stdout.flush()
            ch = sys.stdin.read(1)
            if not ch:
                break
            if picker is not None:
                if ch in ("\x1b",):  # Esc closes picker
                    picker = None
                    continue
                if ch in ("\r", "\n"):
                    # accept selected layout (recorded as a side answer)
                    w.answers["keyboard_layout"] = picker[w.selection]
                    picker = None
                    continue
                if ch in ("\x03",):  # Ctrl-C
                    raise KeyboardInterrupt
                if ch == "\x7f" or ch == "\x08":
                    continue
                if ch in ("\x1b",):
                    continue
                # arrow / movement while picker open
                if ch == "\x1b":
                    continue
                # map printable + arrows
                if ch == "k" or ch == "A":  # up (k or arrow-up)
                    w.selection = (w.selection - 1) % len(picker)
                elif ch == "j" or ch == "B":  # down
                    w.selection = (w.selection + 1) % len(picker)
                continue
            # normal mode
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in ("\r", "\n"):
                # info / choice / text confirm
                if scr["kind"] in ("text", "password"):
                    w.confirm()
                elif scr["kind"] == "choice":
                    w.confirm()
                else:
                    w.confirm()
                help_on = False
                continue
            if ch == "\x7f" or ch == "\x08":  # backspace
                w.backspace()
                continue
            if ch == "T" and scr.get("escape") == "terminal" and scr["kind"] == "info":
                w.escape()
                break
            if ch == "K" and scr["id"] == "language":
                picker = list(KEYBOARD_LAYOUTS)
                w.selection = 0
                continue
            if ch == "?" and scr.get("help"):
                help_on = not help_on
                continue
            if ch in ("\x1b",):
                # On a progress/download screen, Esc means "skip" (advance).
                # Otherwise it's the prefix of an arrow key; read the rest.
                if scr["kind"] == "progress":
                    w.confirm()
                    help_on = False
                    continue
                nxt = sys.stdin.read(2)
                if nxt == "[A":
                    w.move(-1)
                elif nxt == "[B":
                    w.move(1)
                continue
            if scr["kind"] in ("text", "password"):
                if ch.isprintable() and ch not in ("\n", "\r"):
                    w.type_char(ch)
            elif scr["kind"] == "choice":
                # allow j/k too
                if ch == "k":
                    w.move(-1)
                elif ch == "j":
                    w.move(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return w


def main() -> int:
    print(c(DIM, "HermesOS first-boot wizard — type ? for help, T on the hello screen for a terminal.\n"))
    try:
        w = run()
    except KeyboardInterrupt:
        print(c(YEL, "\n[interrupted]"))
        return 1
    if w.went_terminal:
        print(c(YEL, "\nDropped to a plain terminal. Run this wizard again with: python3 firstboot/tui.py"))
        return 0
    print(c(GREEN, "\nWizard complete. Plan:"))
    import json
    print(json.dumps(w.plan(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
