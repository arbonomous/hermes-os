#!/usr/bin/env python3
"""firstboot/tui_demo.py — render a full wizard walkthrough, frame by frame.

This does NOT need a real terminal. It applies a scripted sequence of
keystrokes to the Wizard state machine and prints the TUI render after each
step, so you can see exactly what the live VM screen shows. The same Wizard +
render() path is used by the interactive tui.py.

Run inside the VM for the live version:  python3 firstboot/tui.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tui
from wizard import Wizard

# Keys: ENTER, UP, DOWN, "K" picker, "?", "T" terminal, chars for text.
SCRIPT = [
    ("ENTER", "boot → ready"),
    ("ENTER", "hello → begin"),
    ("DOWN", "language: move to Español"),
    ("UP", "language: back to English (default)"),
    ("K", "language: open keyboard picker"),
    ("DOWN", "picker: highlight UK QWERTY"),
    ("ENTER", "picker: choose UK QWERTY"),
    ("ENTER", "language → confirm English"),
    ("ENTER", "time → accept detected"),
    ("type:Sam", "account_name: type 'Sam'"),
    ("ENTER", "account_name → confirm"),
    ("type:correct-horse-battery", "account_password: type password"),
    ("ENTER", "account_password → confirm (encrypt=no default)"),
    ("DOWN", "brain: look at Light"),
    ("UP", "brain: back to Balanced (default)"),
    ("?", "brain: toggle help"),
    ("?", "brain: toggle help off"),
    ("ENTER", "brain → choose Balanced"),
    ("ENTER", "download → skip (no real download in demo)"),
    ("ENTER", "first_conversation → done"),
]


def apply_key(w: Wizard, key: str):
    if key == "ENTER":
        w.confirm()
    elif key == "UP":
        w.move(-1)
    elif key == "DOWN":
        w.move(1)
    elif key.startswith("type:"):
        for ch in key[5:]:
            w.type_char(ch)
    elif key == "K":
        pass  # picker is a TUI overlay; demo records the answer directly
        w.answers["keyboard_layout"] = "UK QWERTY"
    elif key == "?":
        pass  # help handled in render only


def main() -> int:
    w = Wizard()
    print("#" * 70)
    print("# HermesOS first-boot wizard — scripted walkthrough (tui.py render)")
    print("#" * 70)
    for key, note in SCRIPT:
        apply_key(w, key)
        print(f"\n### key: {key}  →  {note}")
        print(tui.render(w, help_on=(key == "?")))
        if w.done:
            break
    print("\n### FINAL — wizard.plan():")
    import json
    print(json.dumps(w.plan(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
