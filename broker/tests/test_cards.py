"""Tests for card rendering.

The card is the safety UI. Two properties matter most:
  · the model writes none of it
  · a critical card never reassures
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesctl.cards import (
    render_approval,
    render_critical,
    render_refusal,
    render_teaching,
)
from hermesctl.verbs import Verb, load_verb, render_command

V = Path(__file__).resolve().parents[2] / "verbs.d"


def card_for(name, values, **kw):
    v = load_verb(V / name)
    argv = render_command(v, v.execute, values)
    kw.setdefault("changes", "+ 1 thing")
    kw.setdefault("snapshot", True)
    return v, render_approval(v, values, argv=argv, **kw)


def test_standard_card_has_all_four_sections():
    _, card = card_for("pkg.install.yaml", {"names": ["vlc"]})
    for section in ("WHAT THIS DOES", "WHAT CHANGES",
                    "IF YOU CHANGE YOUR MIND"):
        assert section in card
    assert "[Y] Yes, go ahead" in card


def test_sections_appear_in_fixed_order():
    _, card = card_for("pkg.install.yaml", {"names": ["vlc"]})
    order = [card.index(s) for s in
             ("WHAT THIS DOES", "WHAT CHANGES", "IF YOU CHANGE YOUR MIND")]
    assert order == sorted(order)


def test_changes_text_comes_from_caller_not_verb():
    """WHAT CHANGES must be the dry-run result, not verb prose."""
    _, card = card_for("pkg.install.yaml", {"names": ["vlc"]},
                       changes="+ 4 new programs added (18.4 MB)")
    assert "18.4 MB" in card


def test_command_hidden_unless_asked():
    _, card = card_for("pkg.install.yaml", {"names": ["vlc"]})
    assert "/usr/bin/apt-get" not in card
    _, shown = card_for("pkg.install.yaml", {"names": ["vlc"]}, show_command=True)
    assert "/usr/bin/apt-get install -y vlc" in shown


def test_high_risk_asks_for_typed_word_not_yes_no():
    _, card = card_for("pkg.remove.yaml", {"names": ["gimp"]})
    assert "type:  remove" in card
    assert "[Y] Yes" not in card


def test_list_values_read_naturally():
    _, card = card_for("pkg.remove.yaml", {"names": ["gimp", "inkscape"]})
    assert "gimp and inkscape" in card


def test_no_snapshot_says_so_honestly():
    _, card = card_for("pkg.install.yaml", {"names": ["vlc"]}, snapshot=False)
    assert "nothing to undo" in card


def test_prose_is_reflowed_not_raw_yaml():
    """YAML authoring line breaks must not survive into the card."""
    _, card = card_for("pkg.remove.yaml", {"names": ["gimp"]})
    assert "so check the\n" not in card
    for line in card.splitlines():
        assert len(line) <= 64, f"line too wide: {line!r}"


# ── critical ────────────────────────────────────────────────────────────

def test_critical_card_warns_and_denies_the_safety_net():
    v = load_verb(V / "disk.format.yaml")
    vals = {"target": "/dev/disk/by-id/usb-Kingston-0:0"}
    card = render_critical(v, vals, changes="1,204 files, 14 GB.",
                           argv=render_command(v, v.execute, vals))
    assert "PERMANENTLY ERASES DATA" in card
    assert "will NOT bring this back" in card
    assert "type:  erase" in card


def test_critical_card_contains_no_reassurance():
    v = load_verb(V / "disk.format.yaml")
    vals = {"target": "/dev/disk/by-id/usb-Kingston-0:0"}
    card = render_critical(v, vals, changes="1,204 files.",
                           argv=render_command(v, v.execute, vals)).lower()
    for soothing in ("don't worry", "no problem", "undo that",
                     "restore point first", "it's fine", "easy"):
        assert soothing not in card, f"critical card reassures: {soothing!r}"


def test_critical_without_consequence_refuses_to_render():
    """A verb built bypassing the loader must not produce a soft card."""
    bad = Verb(name="x.bad", summary="s", risk="critical", explain="e",
               execute=["/bin/true"], confirm_word=None, consequence=None)
    with pytest.raises(ValueError, match="understates the risk"):
        render_critical(bad, {}, changes="", argv=["/bin/true"])


# ── teaching and refusal ────────────────────────────────────────────────

def test_teaching_card_always_shows_the_literal_command():
    card = render_teaching(
        request="quieter fans", verb_name="fan.set",
        argv=["/usr/bin/asusctl", "fan-curve", "--set", "quiet"],
        explanation="Controls fan speed.", risk="medium")
    assert "/usr/bin/asusctl fan-curve --set quiet" in card
    assert "MEDIUM risk" in card
    assert "forget how to do that" in card


def test_refusal_hands_over_the_keys():
    card = render_refusal("Changing /etc/sudoers would let me give myself power.")
    assert "no-list" in card
    assert "!shell" in card
    # Normalise whitespace: the phrase may be split across a wrapped line.
    assert "your computer" in " ".join(card.lower().split())
