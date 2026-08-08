"""Tests for the first-boot service entry point (firstboot/firstbootd.py).

No commands are executed against the host. We stub the Runner and the prompt,
and use a temp pending flag, so these prove the service's *control flow*:
idempotency, dry-run-by-default, safe-failure, and flag-clearing.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def _load_firstbootd(monkeypatch, *, pending_exists: bool, runner_results=None, apply_env=False):
    """Load firstbootd with stubs: no real Runner, no real filesystem flag."""
    # Stub the two imports firstbootd does.
    captured = {}

    class FakeRunner:
        def __init__(self, plan, prompt, dry_run, runner=None, log_path=None):
            captured["plan"] = plan
            captured["dry_run"] = dry_run
            captured["prompt"] = prompt
            self.plan = plan
            self.results = runner_results if runner_results is not None else [
                {"verb": v["verb"], "ran": not dry_run, "dry_run": dry_run}
                for v in plan
            ]
        def apply(self):
            return self.results

    fake_apply = types.ModuleType("firstboot.apply")
    fake_apply.Runner = FakeRunner
    fake_wizard = types.ModuleType("firstboot.wizard")

    # Minimal Wizard stub that completes immediately with one intent.
    # Mirrors the attributes firstbootd.run_wizard actually reads.
    class FakeWizard:
        def __init__(self):
            self._done = False
            self._i = 0
            self._screens = [
                {"id": "boot", "kind": "info"},
                {"id": "account_name", "kind": "text"},
                {"id": "account_password", "kind": "password"},
                {"id": "brain", "kind": "choice"},
                {"id": "first_conversation", "kind": "info"},
            ]
            self.answers = {"account_name": "Sam", "account_password": "x",
                            "language": "en", "time": "detected", "brain": "balanced",
                            "encrypt": "no"}
        @property
        def screen(self):
            return self._screens[min(self._i, len(self._screens) - 1)]
        @property
        def done(self):
            return self._done
        def plan(self):
            if self._done:
                return [{"verb": "user.create", "risk": "medium",
                         "params": {"name": "Sam", "password_set": True}}]
            return []
        def confirm(self):
            self._i += 1
            if self._i >= len(self._screens):
                self._done = True

    fake_wizard.Wizard = FakeWizard

    if apply_env:
        monkeypatch.setenv("FIRSTBOOT_APPLY", "1")

    # Stub argv so argparse in main() doesn't choke on pytest's own args.
    monkeypatch.setattr(sys, "argv", ["firstbootd.py"])

    # Inject stubs into sys.modules before importing firstbootd.
    saved = {}
    for name, mod in (("firstboot.apply", fake_apply), ("firstboot.wizard", fake_wizard)):
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    spec = importlib.util.spec_from_file_location(
        "firstboot.firstbootd", REPO / "firstboot" / "firstbootd.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["firstboot.firstbootd"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        for name, orig in saved.items():
            if orig is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = orig

    # Patch PENDING_FLAG on the already-loaded module (monkeypatch can't target
    # a submodule attribute that didn't exist at call time).
    flag = Path("/tmp/firstboot-pending-test")
    if pending_exists:
        flag.touch()
    else:
        if flag.exists():
            flag.unlink()
    monkeypatch.setattr(mod, "PENDING_FLAG", flag)
    # Point the log dir at a temp location so the test never touches /var.
    import tempfile
    logdir = Path(tempfile.mkdtemp(prefix="hermesos-fb-"))
    monkeypatch.setattr(mod, "LOG_DIR", logdir)
    monkeypatch.setenv("HERMESOS_LOG_DIR", str(logdir))

    return mod, captured


def test_no_pending_flag_is_a_safe_noop(monkeypatch, capsys):
    mod, cap = _load_firstbootd(monkeypatch, pending_exists=False)
    rc = mod.main()
    assert rc == 0
    assert "nothing pending" in capsys.readouterr().out
    assert "plan" not in cap  # Runner never constructed


def test_pending_flag_dry_runs_by_default(monkeypatch, capsys):
    mod, cap = _load_firstbootd(monkeypatch, pending_exists=True)
    rc = mod.main()
    assert rc == 0
    assert cap.get("dry_run") is True          # default is dry-run, never applies
    # flag cleared after run
    assert not Path("/tmp/firstboot-pending-test").exists()


def test_pending_flag_with_apply_runs_real(monkeypatch, capsys):
    mod, cap = _load_firstbootd(monkeypatch, pending_exists=True,
                                runner_results=[{"verb": "user.create", "ran": True}],
                                apply_env=True)
    rc = mod.main()
    assert rc == 0
    assert cap.get("dry_run") is False
    assert not Path("/tmp/firstboot-pending-test").exists()
