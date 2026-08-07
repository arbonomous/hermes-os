"""Error translation tests.

The promise is "zero cryptic error messages". These check the translation
happens, and — just as important — that an unknown error is passed through
verbatim rather than given an invented meaning.
"""
from __future__ import annotations

import pytest

from hermesctl.errors import explain, friendly_failure

KNOWN = [
    ("E: Could not get lock /var/lib/dpkg/lock-frontend",
     "already installing software"),
    ("E: Unable to locate package vlcc", "couldn't find that program"),
    ("Temporary failure resolving 'archive.ubuntu.com'", "can't reach the internet"),
    ("dpkg: error: No space left on device", "disk is full"),
    ("E: dpkg was interrupted, you must manually run...", "cut off partway"),
    ("mkdir: Permission denied", "wasn't allowed"),
    ("Failed to restart nope.service: Unit nope.service not found.",
     "isn't installed on this computer"),
    ("E: Held broken packages", "clash with what's already installed"),
]


@pytest.mark.parametrize("raw,expected", KNOWN)
def test_known_errors_are_translated(raw, expected):
    e = explain(raw)
    assert e is not None, f"no translation for: {raw}"
    assert expected in e.render()


@pytest.mark.parametrize("raw,_", KNOWN)
def test_translations_never_leak_jargon(raw, _):
    e = explain(raw)
    assert e is not None
    text = e.render().lower()
    for jargon in ("dpkg", "apt-get", "e:", "errno", "stderr", "/var/lib",
                   "systemctl", "exit"):
        assert jargon not in text, f"leaked {jargon!r} for: {raw}"


@pytest.mark.parametrize("raw,_", KNOWN)
def test_every_translation_offers_a_next_step(raw, _):
    e = explain(raw)
    assert e is not None and e.next_step, f"no next step for: {raw}"


def test_unknown_error_is_not_translated():
    assert explain("E: flurble subsystem misaligned") is None


def test_unknown_error_shown_verbatim():
    """Never invent a meaning for an error we don't recognise."""
    msg = friendly_failure("Install vlc",
                           "E: flurble subsystem misaligned\n", snapshot=True)
    assert "flurble subsystem misaligned" in msg
    assert "didn't work" in msg


def test_noise_lines_are_skipped():
    msg = friendly_failure("Install vlc",
                           "Reading package lists...\n"
                           "Building dependency tree...\n"
                           "E: something specific went wrong\n",
                           snapshot=False)
    assert "something specific went wrong" in msg
    assert "Reading package lists" not in msg


def test_snapshot_reassurance_only_when_true():
    with_snap = friendly_failure("Install vlc", "E: boom\n", snapshot=True)
    without = friendly_failure("Install vlc", "E: boom\n", snapshot=False)
    assert "restore point" in with_snap
    assert "restore point" not in without
