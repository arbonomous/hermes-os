#!/usr/bin/env python3
"""Walk hermesd through a beginner conversation.

    python3 hermesd_pkg/demo_hermesd.py

No model — a stub completion stands in, so this shows the loop and the two
routing guards deterministically. A live model would slot into `complete=`.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "broker"))
sys.path.insert(0, str(REPO))

import hermesd_pkg  # noqa: E402
from hermesctl.snapshots import SnapshotBackend, SnapshotError  # noqa: E402


class StubModel:
    """Fixed responses — stands in for a real local model."""
    def __init__(self, scripted: dict[str, str]):
        self.scripted = scripted

    def __call__(self, prompt: str) -> str:
        # ripped straight from the prompt's "User:" line
        user = prompt.rsplit("User:", 1)[-1].strip()
        # crude: match the most specific known phrase
        for phrase, verb in self.scripted.items():
            if phrase in user.lower():
                return verb
        return "REFUSE"


class FakeSnap(SnapshotBackend):
    name = "fake"
    def available(self): return True
    def create(self, label):
        return type("S", (), {"name": "snap", "backend": "fake",
                             "created": "2026-01-01T00:00:00Z", "label": label})()
    def list(self): return []
    def restore(self, n): return "ok"


def scene(title):
    print(f"\n{'─' * 64}\n  {title}\n{'─' * 64}")


def main() -> int:
    tmp = tempfile.mkdtemp()
    # A beginner who phrases things loosely — exactly the eval's hard cases.
    model = StubModel({
        "install vlc": "pkg.install",
        "update my system": "pkg.update",          # a verb that doesn't exist
        "clean my disk": "disk.format",            # vague + destructive
        "wipe /dev/disk/by-id/scsi-sda_xyz": "disk.format",
    })
    hermes = hermesd_pkg.Hermesd(
        complete=model, home=tmp, audit_path=f"{tmp}/audit.jsonl",
        snapshots=FakeSnap(), runner=_null_runner(),
    )

    scene("1 · a normal request")
    t = hermes.run_turn("install vlc", approve=True)
    print(t.card if t.card else t.text)

    scene("2 · the model hallucinates a verb (pkg.update)")
    t = hermes.run_turn("update my system")
    print(t.text)   # must refuse, never run a phantom verb

    scene("3 · vague + destructive ('clean my disk')")
    t = hermes.run_turn("clean my disk")
    print(t.text)   # must Clarify, never a destructive action

    scene("4 · explicit, by-id disk erase — the red card")
    t = hermes.run_turn("wipe /dev/disk/by-id/scsi-sda_xyz",
                        approve=True, typed="erase")
    print(t.card if t.card else t.text)

    scene("5 · the day's history, in plain English")
    print(hermes.summary())

    # the two guards, proven by the audit trail
    decisions = [r["decision"] for r in hermes.audit.records()]
    assert "refused" in decisions, "hallucination was not refused"
    assert any(d == "clarify" for d in decisions), "vague-destructive was not clarified"
    print("\n✓ Guard 1 (reject-and-clarify) and Guard 2 (ambiguity gate) both held.")
    return 0


def _null_runner():
    import subprocess
    class R:
        def __call__(self, argv, **kw):
            return subprocess.CompletedProcess(argv, 0,
                    "Inst vlc (3.0.20-1)\nAfter this operation, 18.4 MB will be used.\n", "")
    return R()


if __name__ == "__main__":
    sys.exit(main())
