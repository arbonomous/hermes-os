"""Tests for the first-boot wizard state machine.

The wizard is pure state — these run headless, no display. They pin the design
rules from docs/07-first-boot.md:

  · one question per screen (single decision each)
  · every screen has a safe default reachable by Enter
  · nothing is permanent (answers recorded, changeable)
  · the T escape is always available (never trap the user)
  · validation rejects empty names / short passwords
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from firstboot.wizard import SCREENS, BY_ID, FLOW, Wizard  # noqa: E402


def walk_to(w: Wizard, screen_id: str, max_steps: int = 30) -> None:
    """Advance until we reach screen_id, typing valid input where needed."""
    steps = 0
    while w.screen_id != screen_id and steps < max_steps:
        scr = w.screen
        if scr["kind"] in ("text", "password"):
            w.typed = "Sam" if scr["id"] == "account_name" else "correct-horse-battery"
        w.confirm()
        steps += 1


def test_screen_count_matches_spec():
    # boot + hello + language + time + name + password + brain + download + first
    assert len(SCREENS) == 9


def test_flow_is_ordered_and_unique():
    assert FLOW == ["boot", "hello", "language", "time", "account_name",
                    "account_password", "brain", "download", "first_conversation"]
    assert len(set(FLOW)) == len(FLOW)


def test_every_choice_has_a_default():
    for s in SCREENS:
        if s.get("kind") == "choice":
            opts = s["options"]
            assert any(o.get("default") for o in opts), f"{s['id']} has no default"


def test_enter_reaches_a_safe_default_on_each_choice():
    for s in SCREENS:
        if s.get("kind") == "choice":
            w = Wizard()
            walk_to(w, s["id"])
            w.confirm()  # accept default
            assert w.answers[s["id"]] in {o["id"] for o in s["options"]}


def test_navigation_wraps():
    w = Wizard()
    walk_to(w, "language")
    assert w.screen_id == "language"
    w.move(1); w.move(1); w.move(1); w.move(1); w.move(1)  # wrap several times
    # still a valid option
    assert 0 <= w.selection < len(w.options())


def test_language_default_is_english():
    w = Wizard()
    walk_to(w, "language")
    w.confirm()
    assert w.answers["language"] == "en"


def test_brain_default_is_balanced():
    w = Wizard()
    walk_to(w, "brain")
    w.confirm()
    assert w.answers["brain"] == "balanced"


def test_empty_name_rejected():
    w = Wizard()
    walk_to(w, "account_name")
    w.typed = ""
    nxt = w.confirm()
    assert nxt == "account_name"          # stayed put
    assert "_error" in w.answers


def test_short_password_rejected():
    w = Wizard()
    walk_to(w, "account_password")
    w.typed = "short"
    nxt = w.confirm()
    assert nxt == "account_password"
    assert "_error" in w.answers


def test_good_password_accepted_and_records_encryption_default():
    w = Wizard()
    walk_to(w, "account_password")
    w.typed = "correct-horse-battery"
    nxt = w.confirm()
    assert nxt == "brain"
    assert w.answers["account_password"] == "correct-horse-battery"
    assert w.answers.get("encrypt") == "no"


def test_terminal_escape_always_available():
    w = Wizard()
    w.escape()
    assert w.went_terminal is True


def test_full_walkthrough_completes():
    w = Wizard()
    steps = 0
    while not w.done and steps < 50:
        scr = w.screen
        if scr["kind"] == "choice":
            pass  # keep default
        elif scr["kind"] in ("text", "password"):
            w.typed = "Sam" if scr["id"] == "account_name" else "correct-horse-battery"
        w.confirm()
        steps += 1
    assert w.done is True
    assert w.answers["language"] == "en"
    assert w.answers["brain"] == "balanced"
    assert w.answers["account_name"] == "Sam"
