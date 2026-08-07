"""Executor tests.

The invariant that matters most: a verb declaring snapshot_before does not
run if a restore point cannot be made. Everything else is downstream of that.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from hermesctl.audit import AuditLog
from hermesctl.executor import Executor
from hermesctl.snapshots import NoSnapshots, Snapshot, SnapshotBackend, SnapshotError
from hermesctl.verbs import load_all

VERBS = Path(__file__).resolve().parents[2] / "verbs.d"


# ── doubles ─────────────────────────────────────────────────────────────

class FakeSnapshots(SnapshotBackend):
    name = "fake"

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.created: list[str] = []

    def available(self):
        return True

    def create(self, label):
        if self.fail:
            raise SnapshotError("I couldn't make a restore point, so I've stopped.")
        self.created.append(label)
        return Snapshot(name=f"snap-{len(self.created)}", backend=self.name,
                        created="2026-01-01T00:00:00Z", label=label)

    def list(self):
        return []

    def restore(self, name):
        return "restored"


class FakeRunner:
    """Stands in for subprocess.run. Records argv, returns scripted results."""

    def __init__(self, results=None):
        self.calls: list[list[str]] = []
        self.kwargs: list[dict] = []
        self.results = results or {}

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        self.kwargs.append(kw)
        key = " ".join(argv)
        for pattern, (rc, out) in self.results.items():
            if pattern in key:
                return subprocess.CompletedProcess(argv, rc, out, "")
        return subprocess.CompletedProcess(argv, 0, "", "")


APT_SIM = (
    "Reading package lists...\n"
    "Inst vlc (3.0.20-1 Ubuntu:24.04/noble [amd64])\n"
    "Inst libvlc5 (3.0.20-1 Ubuntu:24.04/noble [amd64])\n"
    "Conf vlc (3.0.20-1 Ubuntu:24.04/noble [amd64])\n"
    "After this operation, 18.4 MB of additional disk space will be used.\n"
)


def build(*, approve=True, snap=None, runner=None, tmp_path=None, dry=False):
    log = AuditLog(tmp_path / "audit.jsonl")
    snaps = snap if snap is not None else FakeSnapshots()
    run = runner or FakeRunner({"--simulate": (0, APT_SIM)})

    def prompt(card, verb):
        if verb.needs_typed_confirm:
            return verb.confirm_word if approve else "no"
        return approve

    ex = Executor(load_all(VERBS), audit=log, snapshots=snaps,
                  home=str(tmp_path), prompt=prompt, runner=run,
                  dry_run_only=dry)
    return ex, run, snaps, log


# ── the snapshot gate ───────────────────────────────────────────────────

def test_snapshot_failure_aborts_before_running(tmp_path):
    ex, run, _, log = build(snap=FakeSnapshots(fail=True), tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})

    assert not res.ok
    # the real command must never have been reached
    assert not any("install" in c and "--simulate" not in " ".join(c)
                   for c in run.calls), run.calls
    assert "couldn't make a restore point" in res.message
    assert log.records()[-1]["decision"] == "aborted"


def test_snapshot_taken_before_execution(tmp_path):
    ex, run, snaps, _ = build(tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert res.ok
    assert snaps.created, "no snapshot was taken"
    assert res.snapshot is not None


def test_no_snapshot_backend_blocks_mutating_verb(tmp_path):
    ex, run, _, _ = build(snap=NoSnapshots(), tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert not res.ok
    assert "won't make a change I couldn't undo" in res.message


def test_safe_verb_needs_no_snapshot(tmp_path):
    ex, run, snaps, _ = build(snap=NoSnapshots(), tmp_path=tmp_path)
    res = ex.invoke("sys.overview")
    assert res.ok
    assert not any("--simulate" in " ".join(c) for c in run.calls)


# ── approval ────────────────────────────────────────────────────────────

def test_denial_runs_nothing_and_is_logged(tmp_path):
    ex, run, snaps, log = build(approve=False, tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert not res.ok
    assert not snaps.created
    assert not any("-y" in c for c in run.calls)
    assert log.records()[-1]["decision"] == "denied"
    assert "haven't changed anything" in res.message


def test_wrong_confirm_word_is_a_denial(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    run = FakeRunner({"--simulate": (0, "Remv gimp [2.10]\n")})
    ex = Executor(load_all(VERBS), audit=log, snapshots=FakeSnapshots(),
                  home=str(tmp_path), runner=run,
                  prompt=lambda card, verb: "yes")   # verb wants "remove"
    res = ex.invoke("pkg.remove", {"names": ["gimp"]})
    assert not res.ok
    assert log.records()[-1]["decision"] == "denied"


def test_safe_verb_does_not_prompt(tmp_path):
    asked = []
    log = AuditLog(tmp_path / "audit.jsonl")

    def prompt(card, verb):
        asked.append(verb.name)
        return True

    ex = Executor(load_all(VERBS), audit=log, snapshots=FakeSnapshots(),
                  home=str(tmp_path), prompt=prompt, runner=FakeRunner())
    ex.invoke("sys.overview")
    assert asked == []


# ── execution hygiene ───────────────────────────────────────────────────

def test_never_uses_a_shell(tmp_path):
    ex, run, _, _ = build(tmp_path=tmp_path)
    ex.invoke("pkg.install", {"names": ["vlc"]})
    for kw in run.kwargs:
        assert kw.get("shell") is False, "a command was run through a shell"


def test_environment_is_sanitised(tmp_path):
    ex, run, _, _ = build(tmp_path=tmp_path)
    ex.invoke("pkg.install", {"names": ["vlc"]})
    env = run.kwargs[-1]["env"]
    assert env["PATH"] == "/usr/sbin:/usr/bin:/sbin:/bin"
    assert "LD_PRELOAD" not in env
    assert env["LC_ALL"] == "C"


def test_argv_is_exactly_what_the_verb_declared(tmp_path):
    ex, run, _, _ = build(tmp_path=tmp_path)
    ex.invoke("pkg.install", {"names": ["vlc", "gimp"]})
    assert run.calls[-1] == ["/usr/bin/apt-get", "install", "-y", "vlc", "gimp"]


def test_injection_never_reaches_the_runner(tmp_path):
    ex, run, _, log = build(tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc; rm -rf /"]})
    assert not res.ok
    assert run.calls == []
    assert log.records()[-1]["decision"] == "refused"


def test_unknown_verb_is_friendly(tmp_path):
    ex, run, _, log = build(tmp_path=tmp_path)
    res = ex.invoke("fan.set", {"speed": "quiet"})
    assert not res.ok
    assert "don't know how to do" in res.message
    assert run.calls == []


def test_unknown_argument_refused(tmp_path):
    ex, run, _, _ = build(tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"], "force": True})
    assert not res.ok
    assert run.calls == []


# ── failures explained like a person would ──────────────────────────────

def test_failure_message_has_no_raw_exit_code(tmp_path):
    run = FakeRunner({
        "--simulate": (0, APT_SIM),
        "install -y": (100, "E: Could not get lock /var/lib/dpkg/lock-frontend\n"),
    })
    ex, run, _, _ = build(runner=run, tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert not res.ok
    # The dpkg lock is a known error, so the user gets the translation
    # rather than apt's wording.
    assert "already installing software" in res.message
    assert "dpkg" not in res.message
    assert "exit code" not in res.message.lower()
    assert "100" not in res.message


def test_failure_message_has_no_unformatted_placeholder(tmp_path):
    """A leaked {names} in the headline is garbage to a beginner."""
    run = FakeRunner({"--simulate": (0, APT_SIM), "install -y": (100, "E: boom\n")})
    ex, run, _, _ = build(runner=run, tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert "{" not in res.message and "}" not in res.message
    assert "Install vlc" in res.message


def test_specific_reason_beats_generic_wording(tmp_path):
    """'took too long' is more useful than 'that didn't work'."""
    class Slow(FakeRunner):
        def __call__(self, argv, **kw):
            self.calls.append(list(argv)); self.kwargs.append(kw)
            if "--simulate" in argv:
                return subprocess.CompletedProcess(argv, 0, APT_SIM, "")
            raise subprocess.TimeoutExpired(argv, 600)

    ex, run, _, _ = build(runner=Slow(), tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert res.message.startswith("That took too long")
    assert "undo that" in res.message


def test_failure_offers_the_restore_point(tmp_path):
    run = FakeRunner({"--simulate": (0, APT_SIM), "install -y": (100, "E: boom\n")})
    ex, run, _, _ = build(runner=run, tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert "restore point" in res.message
    assert "Nothing is broken" in res.message


def test_unrecognised_error_is_shown_verbatim(tmp_path):
    """An unfamiliar real error beats an invented friendly one."""
    run = FakeRunner({"--simulate": (0, APT_SIM),
                      "install -y": (1, "E: flurble subsystem misaligned\n")})
    ex, run, _, _ = build(runner=run, tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert "flurble subsystem misaligned" in res.message


def test_missing_binary_is_explained(tmp_path):
    class Missing(FakeRunner):
        def __call__(self, argv, **kw):
            self.calls.append(list(argv))
            self.kwargs.append(kw)
            if "--simulate" in argv:
                return subprocess.CompletedProcess(argv, 0, APT_SIM, "")
            raise FileNotFoundError()

    ex, run, _, _ = build(runner=Missing(), tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert not res.ok
    assert "isn't installed" in res.message


def test_timeout_is_explained(tmp_path):
    class Slow(FakeRunner):
        def __call__(self, argv, **kw):
            self.calls.append(list(argv))
            self.kwargs.append(kw)
            if "--simulate" in argv:
                return subprocess.CompletedProcess(argv, 0, APT_SIM, "")
            raise subprocess.TimeoutExpired(argv, 600)

    ex, run, _, _ = build(runner=Slow(), tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert "took too long" in res.message


# ── dry-run mode ────────────────────────────────────────────────────────

def test_global_dry_run_never_executes(tmp_path):
    ex, run, snaps, _ = build(dry=True, tmp_path=tmp_path)
    res = ex.invoke("pkg.install", {"names": ["vlc"]})
    assert res.ok
    assert not snaps.created
    assert all("--simulate" in " ".join(c) for c in run.calls)
    assert "Dry run" in res.message


# ── audit completeness ──────────────────────────────────────────────────

def test_every_outcome_is_audited(tmp_path):
    ex, _, _, log = build(tmp_path=tmp_path)
    ex.invoke("pkg.install", {"names": ["vlc"]})
    ex.invoke("nope.nope")
    ex.invoke("pkg.install", {"names": ["bad; rm"]})
    decisions = [r["decision"] for r in log.records()]
    assert decisions == ["approved", "unknown", "refused"]
    ok, msg = log.verify()
    assert ok, msg
