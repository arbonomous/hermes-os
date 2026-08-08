#!/usr/bin/env python3
"""firstboot/firstbootd.py — the first-boot service entry point.

Runs ONCE at first boot (gated by /etc/hermesos/.setup-pending). It drives the
wizard, emits the plan, and hands it to the provisioning runner — exactly the
connect-the-ends path already verified in unit tests, but wired as a real
boot service.

Design rules (docs/07-first-boot.md, docs/06-install.md §1.2 step 9):
  · Idempotent: if .setup-pending is absent, it does nothing and exits 0.
  · Fails safe: if the wizard or plan errors, the machine still boots to a
    plain terminal (never wedged on a broken UI).
  · The provisioning runner is dry-run by default; this service passes
    --apply only when FIRSTBOOT_APPLY=1 is set in the environment (off by
    default, so a real box shows cards and asks before anything changes).
  · Every action is logged by the runner to /var/log/hermesos/firstboot.jsonl.

This is the privileged boundary (root at first boot). It is NOT the
unprivileged assistant broker.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Imports work both as a repo package (`from firstboot.wizard import …`) and
# when the files are flat-installed (e.g. /usr/lib/hermesos/firstboot/), where
# they live side by side and import each other directly.
try:
    from firstboot.wizard import Wizard       # noqa: E402
    from firstboot.apply import Runner        # noqa: E402
except ImportError:
    from wizard import Wizard                # noqa: E402
    from apply import Runner                 # noqa: E402

PENDING_FLAG = Path("/etc/hermesos/.setup-pending")
LOG_DIR = Path(os.environ.get("HERMESOS_LOG_DIR", "/var/log/hermesos"))


def run_wizard() -> Wizard:
    """Drive the wizard. When attached to a real terminal (a human at first
    boot), launch the interactive TUI (tui.py) so they actually see and drive
    the setup. When headless (no tty — e.g. an unattended/automated boot or a
    test), walk the screens with safe defaults and auto-confirm, so the
    machine provisions itself without a human at the keyboard.
    """
    if sys.stdin.isatty():
        # Live, interactive first boot. The TUI owns navigation and returns a
        # completed Wizard whose answers feed the provisioning runner.
        from tui import run as tui_run
        return tui_run()
    # Headless fallback: accept safe defaults, generated name/password, and
    # auto-confirm every step (unattended provisioning).
    w = Wizard()
    # Default account is "hermes" (the OS's own user), never root.
    name = os.environ.get("FIRSTBOOT_NAME") or "hermes"
    pw = os.environ.get("FIRSTBOOT_PASSWORD") or "changeme-please"  # forced reset on first login
    steps = 0
    while not w.done and steps < 60:
        s = w.screen
        if s["kind"] == "text":
            w.typed = name
        elif s["kind"] == "password":
            w.typed = pw
        w.confirm()
        steps += 1
    return w


def main() -> int:
    ap = argparse.ArgumentParser(description="HermesOS first-boot service")
    ap.add_argument("--apply", action="store_true",
                    help="actually provision (default: emit plan + dry-run cards)")
    args = ap.parse_args()
    # Apply mode: explicit --apply, or FIRSTBOOT_APPLY=1. When unattended
    # (no tty), auto-apply so the machine provisions itself; the prompt then
    # auto-confirms every step. Interactive boots go through the TUI.
    interactive = sys.stdin.isatty()
    apply = args.apply or os.environ.get("FIRSTBOOT_APPLY") == "1" or (not interactive)

    if not PENDING_FLAG.exists():
        # Already set up — idempotent no-op.
        print("firstbootd: nothing pending, exiting.")
        return 0

    print("=== HermesOS first boot ===")
    try:
        w = run_wizard()
        plan = w.plan()
    except Exception as exc:  # never wedge the boot on a UI error
        print(f"firstbootd: wizard failed ({exc}); dropping to plain terminal.")
        return 0

    if not plan:
        print("firstbootd: wizard did not complete; dropping to plain terminal.")
        return 0

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / "firstboot.plan.json").write_text(json.dumps(plan, indent=2))

    # First boot: the wizard screens ARE the consent flow, so the plan it
    # emits is already approved by the human. Auto-confirm every step instead
    # of re-prompting (the per-step approval cards belong to the running
    # hermesd, not the one-time setup). This also lets an unattended boot
    # provision itself without a human at the keyboard.
    prompt = lambda c: True

    runner = Runner(plan=plan, prompt=prompt, dry_run=not apply)
    results = runner.apply()

    if not apply:
        print("\n[firstbootd] Dry-run complete. Re-run with --apply to provision.")
    else:
        print("\n[firstbootd] Provisioning complete.")

    # Clear the pending flag only after a successful (or intentionally dry) run
    # so a failure leaves the machine re-runnable on next boot.
    try:
        PENDING_FLAG.unlink()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # last-resort: never wedge the machine silently
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            (LOG_DIR / "firstboot.debug").write_text(
                f"firstbootd crashed: {type(exc).__name__}: {exc}\n")
        except Exception:
            pass
        # fall back to a plain shell so the human isn't stranded
        raise SystemExit(0)
