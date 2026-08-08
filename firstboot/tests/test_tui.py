"""Tests for the terminal TUI renderer (firstboot/tui.py).

These prove the TUI renders the wizard's screens faithfully and that a stale
validation error is cleared once the user starts typing — without needing a
real terminal (render() is pure given a Wizard).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "firstboot"))

import tui
from wizard import Wizard


def test_render_shows_title_and_footer():
    w = Wizard()
    out = tui.render(w)
    assert "Hermes" in out                      # first screen title
    assert "press Enter" in out.lower() or "Enter" in out


def test_choice_screen_shows_options_and_default_marker():
    w = Wizard()
    # advance to language (a choice screen)
    w.confirm()  # boot
    w.confirm()  # hello
    out = tui.render(w)
    assert "English" in out and "Español" in out
    assert "[default]" in out                  # default marker rendered
    assert "▸" in out                           # selection marker rendered


def test_password_screen_masks_input():
    w = Wizard()
    # boot, hello, language, time, account_name(typed), account_password
    w.confirm(); w.confirm()                    # boot, hello
    w.confirm()                                 # language (default)
    w.confirm()                                 # time (default)
    w.typed = "Sam"; w.confirm()                # account_name
    w.type_char("s"); w.type_char("e"); w.type_char("c")
    out = tui.render(w)
    assert "sec" not in out                     # plaintext must NOT appear
    assert "***" in out or "▌" in out           # masked chars or caret shown


def test_stale_error_clears_when_typing():
    w = Wizard()
    w.confirm(); w.confirm(); w.confirm(); w.confirm()   # -> account_name
    w.confirm()                                 # empty -> validation error
    assert w.answers.get("_error")
    rendered_with_err = tui.render(w)
    assert "! " in rendered_with_err            # error visible
    w.type_char("S")                            # user starts typing
    assert "_error" not in w.answers
    assert "! " not in tui.render(w)


def test_brain_help_overlay_renders():
    w = Wizard()
    w.confirm(); w.confirm(); w.confirm(); w.confirm()   # up to account_name
    w.typed = "Sam"; w.confirm()                # account_name
    w.typed = "correct-horse"; w.confirm()      # account_password
    assert w.screen_id == "brain"              # before confirming brain
    out = tui.render(w, help_on=True)
    assert "language model" in out              # help text rendered
