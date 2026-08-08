"""Tests for the first-boot provisioning runner (firstboot/apply.py).

These run headless with no commands executed (dry_run default) and with a
stub prompt, so they prove the *gating and rendering* logic without ever
touching the host. Real execution is exercised separately inside the Lima VM.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from firstboot.apply import Runner, STEPS, TYPED_CONFIRM       # noqa: E402
from firstboot.wizard import Wizard                            # noqa: E402


def _complete_plan(overrides: dict | None = None) -> list[dict]:
    w = Wizard()
    steps = 0
    while not w.done and steps < 50:
        s = w.screen
        if s["kind"] in ("text", "password"):
            w.typed = "Sam" if s["id"] == "account_name" else "correct-horse-battery"
        w.confirm()
        steps += 1
    if overrides:
        w.answers.update(overrides)
    return w.plan()


def test_all_plan_verbs_have_a_provisioning_step():
    # Every intent the wizard can emit must be implementable here; otherwise
    # a finished wizard could silently skip an action.
    for verb in ("user.create", "locale.set", "disk.encrypt", "model.download"):
        assert verb in STEPS, f"{verb} has no provisioning step"


def test_dry_run_is_the_default_and_runs_nothing():
    calls: list = []
    def fake_run(*a, **k):
        calls.append(a)
        class R: returncode = 0; stdout = ""; stderr = ""
        return R()
    plan = _complete_plan()
    r = Runner(plan=plan, prompt=lambda c: True, dry_run=True, runner=fake_run)
    results = r.apply()
    # no command executed in dry-run
    assert calls == [], "dry_run must not execute anything"
    # every intent produced a dry_run record
    assert all(res.get("dry_run") for res in results), results
    assert [res["verb"] for res in results] == [
        "user.create", "locale.set", "model.download"
    ]


def test_dry_run_renders_the_exact_command():
    plan = _complete_plan()
    r = Runner(plan=plan, prompt=lambda c: True, dry_run=True, runner=lambda *a, **k: None)
    r.apply()
    user_step = next(x for x in r.results if x["verb"] == "user.create")
    assert user_step["would_run"] == [
        ["/usr/sbin/useradd", "-m", "-G", "sudo", "-c", "Sam", "Sam"]
    ]


def test_locale_detected_uses_auto_timezone():
    plan = _complete_plan({"time": "detected"})
    r = Runner(plan=plan, prompt=lambda c: True, dry_run=True, runner=lambda *a, **k: None)
    r.apply()
    loc = next(x for x in r.results if x["verb"] == "locale.set")
    cmds = loc["would_run"]
    assert ["/usr/bin/timedatectl", "set-timezone", "auto"] in cmds


def test_encryption_requires_typed_confirm_and_is_skipped_by_default():
    plan = _complete_plan({"encrypt": "yes"})
    # user types the wrong thing -> skipped, not run
    r = Runner(plan=plan, prompt=lambda c: "nope", dry_run=False,
               runner=lambda *a, **k: None)
    r.apply()
    enc = next(x for x in r.results if x["verb"] == "disk.encrypt")
    assert enc["ran"] is False
    assert enc["decision"] == "skipped"


def test_encryption_runs_only_with_exact_typed_word():
    plan = _complete_plan({"encrypt": "yes"})
    calls: list = []
    def fake_run(argv, **k):
        calls.append(argv)
        class R: returncode = 0; stdout = ""; stderr = ""
        return R()
    r = Runner(plan=plan, prompt=lambda c: TYPED_CONFIRM["disk.encrypt"],
               dry_run=False, runner=fake_run)
    r.apply()
    enc = next(x for x in r.results if x["verb"] == "disk.encrypt")
    assert enc["ran"] is True
    # the enable command is the only allowlisted crypto action in v0.1
    assert enc["steps"][0]["argv"][:3] == ["/usr/sbin/deb-systemd-helper", "enable", "hermesos-encrypt"]


def test_skip_brain_omits_model_download_even_in_real_mode():
    plan = _complete_plan({"brain": "skip"})
    r = Runner(plan=plan, prompt=lambda c: True, dry_run=False,
               runner=lambda *a, **k: None)
    r.apply()
    assert all(x["verb"] != "model.download" for x in r.results)


def test_runner_never_constructs_commands_from_unvalidated_text():
    # The card/argv builders receive only validated params from the wizard.
    # Confirm the disk.encrypt builder ignores any stray key a caller passes.
    card, argv = STEPS["disk.encrypt"]({"scope": "root", "evil": "rm -rf /"})
    assert argv == [["/usr/sbin/deb-systemd-helper", "enable", "hermesos-encrypt"]]
    assert all("rm -rf" not in line for line in card)
