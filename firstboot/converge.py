#!/usr/bin/env python3
"""firstboot/converge.py — run the wizard's plan at real first boot.

This is the privileged glue: load a finished wizard's answers (plan.json),
render each approval card, and — only with explicit confirmation — apply it.

SAFETY:
  · Default mode is --dry-run: it prints every card and the exact command
    that WOULD run, then stops. Nothing is changed.
  · Real mode (--apply) still asks per step; disk encryption requires the
    typed word "encrypt-this-disk".
  · Every step is logged to /var/log/hermesos/firstboot.jsonl.

This script is meant to run ONCE as root at first boot inside the protected
HermesOS environment (e.g. the Lima VM, or a real install), NOT on the
host Mac. It is the only place first boot runs privileged commands.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from firstboot.apply import Runner  # noqa: E402


def _prompt(text: str) -> object:
    try:
        ans = input(text).strip()
    except EOFError:
        return False
    return ans


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply a HermesOS first-boot plan.")
    ap.add_argument("--plan", required=True, help="path to a wizard plan JSON")
    ap.add_argument("--apply", action="store_true",
                    help="actually run (default: dry-run, prints only)")
    args = ap.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"No plan file at {plan_path}", file=sys.stderr)
        return 2
    plan = json.loads(plan_path.read_text())

    mode = "APPLY (real)" if args.apply else "DRY RUN (no changes)"
    print(f"=== HermesOS first boot — {mode} ===\n")

    runner = Runner(plan=plan, prompt=_prompt, dry_run=not args.apply)
    results = runner.apply()

    print("\n=== Summary ===")
    for r in results:
        verb = r.get("verb", "?")
        if r.get("ran"):
            print(f"  [ran]     {verb}")
        elif r.get("dry_run"):
            print(f"  [dry-run] {verb}")
        elif r.get("decision") == "skipped":
            print(f"  [skipped] {verb}")
        else:
            print(f"  [n/a]     {verb}: {r.get('error','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
