#!/usr/bin/env python3
"""Render every card type with real verb definitions. Visual proof.

    ./.venv/bin/python demo_cards.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hermesctl.cards import (
    render_approval,
    render_critical,
    render_refusal,
    render_teaching,
)
from hermesctl.verbs import load_verb, render_command

V = Path(__file__).resolve().parents[1] / "verbs.d"


def show(title, body):
    print(f"\n{'═' * 64}\n  {title}\n{'═' * 64}")
    print(body)


# medium — the everyday card
v = load_verb(V / "pkg.install.yaml")
vals = {"names": ["vlc"]}
show("MEDIUM · install", render_approval(
    v, vals,
    changes="+ 4 new programs added (18.4 MB)\n· Nothing is removed or overwritten",
    argv=render_command(v, v.execute, vals),
    snapshot=True))

# high — typed confirmation
v = load_verb(V / "pkg.remove.yaml")
vals = {"names": ["gimp", "inkscape"]}
show("HIGH · remove (typed confirm)", render_approval(
    v, vals,
    changes="- 2 programs removed (241 MB freed)\n- 3 other programs depend on these",
    argv=render_command(v, v.execute, vals),
    snapshot=True))

# same card, command expanded via '?'
show("HIGH · with '?' pressed", render_approval(
    v, vals,
    changes="- 2 programs removed (241 MB freed)",
    argv=render_command(v, v.execute, vals),
    snapshot=True, show_command=True))

# critical — no warmth
v = load_verb(V / "disk.format.yaml")
vals = {"target": "/dev/disk/by-id/usb-Kingston_DataTraveler-0:0"}
show("CRITICAL · erase disk", render_critical(
    v, vals,
    changes="1,204 files, 14 GB.",
    argv=render_command(v, v.execute, vals)))

# teaching
show("TEACHING · unknown ability", render_teaching(
    request="make the fans quieter when the laptop is cool",
    verb_name="fan.set-profile",
    argv=["/usr/bin/asusctl", "fan-curve", "--set", "quiet"],
    explanation="Controls how fast your fans spin. Reversible — you can "
                "always set it back to automatic.",
    risk="medium"))

# refusal
show("REFUSAL · forbidden", render_refusal(
    "Changing /etc/sudoers would let me give myself more power, so I'm "
    "not allowed to touch it, ever, even if you ask."))

print()
