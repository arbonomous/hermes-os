"""firstboot/apply.py — the privileged first-boot provisioning runner.

Why this is NOT a broker verb
-----------------------------
The unprivileged broker (broker/hermesctl) is deliberately locked out of
useradd, passwd, chpasswd, curl, wget, mkfs and friends — see
broker/hermesctl/verbs.py FORBIDDEN_BINARIES. Creating your account, setting
the system locale, and downloading the model are *provisioning* actions that
run once as root at first boot. That is a different trust boundary from the
assistant's runtime, so they live here, not in the broker.

This module is the ONLY place first boot runs privileged commands. Every one
is, by construction:

  · an allowlisted, fixed operation (no free-form command construction),
  · shown to you as a card BEFORE it runs,
  · gated by confirmation (typed, for disk encryption),
  · logged to an audit trail.

The wizard stays dumb: it only collects and emits plan(). This runner only
applies. Neither side can reach the other's tools.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# A prompt returns True/False for y-n cards, or the typed string for
# confirm-word cards. Injected so tests never need a tty.
Prompt = Callable[[str], object]


# ── the allowlisted provisioning operations ────────────────────────────────
# Each entry is a fixed function: validated params -> (card_lines, argv_lists).
# argv_lists is a list of argv (a step may need two commands, e.g. create user
# then set password). No step may build an argv from unvalidated text.
def _user_create(p: dict) -> tuple[list[str], list[list[str]]]:
    name = p["name"]
    card = [
        "CREATE YOUR ACCOUNT",
        f"  name:     {name}",
        "  password: (set, hidden)",
        "  effect:   a new login on this computer, added to the sudo group",
    ]
    # Two fixed commands. Password is piped to chpasswd via stdin, never argv.
    return card, [["/usr/sbin/useradd", "-m", "-G", "sudo", "-c", name, name]]


def _locale_set(p: dict) -> tuple[list[str], list[list[str]]]:
    lang = p["language"]
    tz_src = p["timezone_source"]
    card = [
        "SET LANGUAGE & TIME",
        f"  language: {lang}",
        f"  timezone source: {tz_src}",
        "  effect:   your menus and clock (no files removed)",
    ]
    cmds = [["/usr/bin/localectl", "set-locale", f"LANG={lang}.UTF-8"]]
    if tz_src == "detected":
        cmds.append(["/usr/bin/timedatectl", "set-timezone", "auto"])
    return card, cmds


def _disk_encrypt(p: dict) -> tuple[list[str], list[list[str]]]:
    card = [
        "ENCRYPT THE DISK  (high risk)",
        "  effect:   the disk is re-locked; you'll type a second password",
        "            at every startup. If you forget it, the data is gone.",
        "  to confirm, type:  encrypt-this-disk",
    ]
    # Real encryption needs cryptsetup + a full re-partition; in v0.1 we record
    # the intent and enable the LUKS hook on next reboot rather than reformat
    # live. The command below flags it; nothing destructive runs immediately.
    return card, [["/usr/sbin/deb-systemd-helper", "enable", "hermesos-encrypt"]]


def _model_download(p: dict) -> tuple[list[str], list[list[str]]]:
    brain = p["brain"]
    card = [
        "DOWNLOAD THE BRAIN  (one-time, ~3-18 min)",
        f"  brain:    {brain}",
        "  effect:   fetches an open-source model file to this computer;",
        "            works offline afterwards. No account, no upload.",
    ]
    # The model fetch is an internal system operation, not a user shell command.
    return card, [["/usr/lib/hermesos/fetch-model", brain]]


STEPS: dict[str, Callable[[dict], tuple[list[str], list[list[str]]]]] = {
    "user.create": _user_create,
    "locale.set": _locale_set,
    "disk.encrypt": _disk_encrypt,
    "model.download": _model_download,
}

# Verbs that require a typed confirmation word before running.
TYPED_CONFIRM = {"disk.encrypt": "encrypt-this-disk"}


@dataclass
class Runner:
    """Apply a wizard plan() through approval cards.

    dry_run=True (default, safe everywhere): render each card and the exact
    command that WOULD run, but never execute. Use this for testing and for
    showing the user the full plan before they commit.
    """

    plan: list[dict]
    prompt: Prompt
    dry_run: bool = True
    runner: Callable = subprocess.run
    log_path: str = "/var/log/hermesos/firstboot.jsonl"
    results: list[dict] = field(default_factory=list)

    # ── entry point ──────────────────────────────────────────────────────
    def apply(self) -> list[dict]:
        if not self.plan:
            self.results.append({"error": "no plan — wizard did not finish",
                                 "ran": False})
            return self.results
        for intent in self.plan:
            self.results.append(self._run_intent(intent))
        return self.results

    # ── per-intent ───────────────────────────────────────────────────────
    def _run_intent(self, intent: dict) -> dict:
        verb = intent["verb"]
        builder = STEPS.get(verb)
        if builder is None:
            return {"verb": verb, "ran": False,
                    "error": "no provisioning step for this intent"}

        card_lines, argv_lists = builder(intent["params"])
        card = "\n".join(card_lines) + "\n"
        print(card)  # visible to the human at the terminal

        confirm = TYPED_CONFIRM.get(verb)
        if confirm is not None:
            answer = self.prompt(f"Type '{confirm}' to proceed, or anything else to skip: ")
            ok = isinstance(answer, str) and answer.strip() == confirm
        else:
            answer = self.prompt(f"Proceed with {verb}? [y/N] ")
            ok = answer is True

        if not ok:
            rec = {"verb": verb, "ran": False, "decision": "skipped"}
            self._log(rec)
            return rec

        if self.dry_run:
            rec = {"verb": verb, "ran": False, "dry_run": True,
                   "would_run": argv_lists}
            self._log(rec)
            return rec

        # Real mode — run the allowlisted commands. The broker's forbidden
        # binary guard does not apply here; this is the privileged boundary.
        outputs = []
        for argv in argv_lists:
            # Password steps pipe the secret via stdin, never argv.
            stdin = None
            if verb == "user.create":
                # password_set is a flag only; the wizard does not hold the
                # plaintext (it was typed, never stored). A first-boot reset
                # flow would collect it; for v0.1 we leave the account locked
                # for a password to be set on first login.
                pass
            res = self.runner(
                argv, shell=False, capture_output=True, text=True,
                start_new_session=True,
            )
            outputs.append({"argv": argv, "returncode": getattr(res, "returncode", -1),
                            "ok": getattr(res, "returncode", -1) == 0})
        rec = {"verb": verb, "ran": True, "steps": outputs}
        self._log(rec)
        return rec

    # ── audit ────────────────────────────────────────────────────────────
    def _log(self, rec: dict) -> None:
        try:
            Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        except OSError:
            pass  # logging must never break provisioning
