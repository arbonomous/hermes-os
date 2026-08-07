"""Tests for hermesd + the router.

The router is where the verb-routing reality-check lives as *code*. These tests
use a stub completion function (no model, deterministic) so they pin the two
guards the eval proved we need:

  G1 reject-and-clarify — a model-named verb not in the catalogue is refused,
      never blindly invoked. (eval showed llama + qwen both invent pkg.update.)
  G2 ambiguity gate — a critical verb with no concrete target and no explicit
      destructive word becomes a Clarify, never a destructive action.
      (eval showed both models route "clean my disk" -> disk.format.)
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]  # hermes-os/
sys.path.insert(0, str(REPO / "broker"))

import hermesd_pkg  # noqa: E402
from hermesctl.snapshots import SnapshotBackend, SnapshotError  # noqa: E402
from hermesd_pkg import Clarify, Hermesd, Refuse, Routed, Router  # noqa: E402


class StubModel:
    """Returns a fixed verb name (or REFUSE) regardless of input."""
    def __init__(self, returns: str):
        self.returns = returns

    def __call__(self, prompt: str) -> str:
        return self.returns


def make_router(returns: str) -> Router:
    from hermesctl.verbs import load_all
    verbs = load_all(REPO / "verbs.d")
    return Router(verbs, StubModel(returns))


# ── G1: reject-and-clarify ────────────────────────────────────────────────

def test_real_verb_routes():
    r = make_router("pkg.install").route("install vlc")
    assert isinstance(r, Routed) and r.verb == "pkg.install"


def test_refuse_marker_refuses():
    r = make_router("REFUSE").route("write me a poem")
    assert isinstance(r, Refuse)
    assert "don't know" in r.reason or "can't" in r.reason.lower()


def test_hallucinated_verb_is_refused_not_invoked():
    r = make_router("pkg.update").route("update my system")
    assert isinstance(r, Refuse)
    assert "pkg.update" in r.reason


def test_other_hallucination_refused():
    r = make_router("svc.list").route("what services")
    assert isinstance(r, Refuse)


def test_empty_model_output_refused():
    r = make_router("").route("hello?")
    assert isinstance(r, Refuse)


# ── G2: ambiguity gate for destructive verbs ────────────────────────────────

def test_vague_destructive_is_clarified():
    r = make_router("disk.format").route("clean my disk")
    assert isinstance(r, Clarify)
    assert "which disk" in r.question.lower() or "usb" in r.question.lower()


def test_explicit_destructive_word_routes():
    r = make_router("disk.format").route("wipe everything on /dev/sdb")
    assert isinstance(r, Routed) and r.verb == "disk.format"


def test_explicit_target_routes():
    r = make_router("disk.format").route("format the disk /dev/sdc")
    assert isinstance(r, Routed)


def test_args_extracted():
    r = make_router("pkg.install").route("install vlc and firefox")
    assert isinstance(r, Routed)
    assert r.args.get("names") == ["vlc", "firefox"]


def test_device_arg_extracted():
    r = make_router("disk.format").route("wipe /dev/sdb")
    assert isinstance(r, Routed)
    # router pulls the device token; the broker later enforces by-id paths
    assert r.args.get("target") == "/dev/sdb"


# ── the full loop ───────────────────────────────────────────────────────────

class FakeSnapshots(SnapshotBackend):
    name = "fake"

    def __init__(self, fail=False):
        self.fail = fail
        self.made = []

    def available(self):
        return not self.fail

    def create(self, label):
        if self.fail:
            raise SnapshotError("no restore point")
        self.made.append(label)
        return type("S", (), {"name": "snap", "backend": "fake",
                             "created": "2026-01-01T00:00:00Z", "label": label})()

    def list(self):
        return []

    def restore(self, name):
        return "ok"


class FakeRunner:
    def __init__(self, results=None):
        self.calls = []
        self.kwargs = []
        self.results = results or {}

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        self.kwargs.append(kw)
        for pat, (rc, out) in self.results.items():
            if pat in " ".join(argv):
                return subprocess.CompletedProcess(argv, rc, out, "")
        return subprocess.CompletedProcess(argv, 0, "", "")


APT_SIM = ("Inst vlc (3.0.20-1)\nAfter this operation, 18.4 MB will be used.\n")


def make_hermesd(returns: str, *, approve=True, snap_fail=False, tmp_path=None,
                 runner=None):
    tmp = tmp_path or tempfile.mkdtemp()
    h = Hermesd(
        complete=StubModel(returns), home=tmp,
        audit_path=str(Path(tmp) / "audit.jsonl"),
        snapshots=FakeSnapshots(fail=snap_fail),
        runner=runner or FakeRunner({"--simulate": (0, APT_SIM)}),
    )
    return h


def test_safe_verb_runs_end_to_end():
    h = make_hermesd("pkg.install")
    turn = h.run_turn("install vlc", approve=True)
    assert "Install" in turn.card and "vlc" in turn.card


def test_hallucination_never_reaches_executor():
    h = make_hermesd("pkg.update")
    turn = h.run_turn("update my system", approve=True)
    assert "pkg.update" in turn.text
    assert h.audit.records()[-1]["decision"] == "refused"


def test_vague_destructive_never_executes():
    h = make_hermesd("disk.format")
    # "clean my disk" has no target -> Clarify, never an action/card
    turn = h.run_turn("clean my disk", approve=True)
    assert "which disk" in turn.text.lower()
    assert turn.card == ""
    # a bare /dev/sdb (not a by-id path) is refused by the broker's validation,
    # not executed. The danger of "clean my disk" -> destructive verb is closed.
    turn2 = h.run_turn("wipe /dev/sdb", approve=True, typed="erase")
    assert "by-id" in turn2.text or "no-list" in turn2.text


def test_critical_verb_shows_red_card():
    h = make_hermesd("disk.format")
    by_id = "/dev/disk/by-id/scsi-SATA_example_123"
    turn = h.run_turn(f"wipe {by_id}", approve=True, typed="erase")
    assert "Erase" in turn.card or "erase" in turn.card.lower()


def test_denial_runs_nothing():
    h = make_hermesd("pkg.install", approve=False)
    turn = h.run_turn("install vlc", approve=False)
    assert h.audit.records()[-1]["decision"] == "denied"


def test_summary_is_readable():
    h = make_hermesd("pkg.install")
    h.run_turn("install vlc", approve=True)
    prose = h.summary()
    assert "install" in prose.lower()
