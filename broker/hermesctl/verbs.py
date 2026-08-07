"""Verb definitions: loading, and the guard that no verb may pass.

A verb is a typed, named operation. The model chooses which verb to invoke;
it never writes the command, the risk tier, or the warning text.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .validate import ArgSpec

RISK_ORDER = ("safe", "low", "medium", "high", "critical")


class VerbError(Exception):
    """A verb definition is malformed, or forbidden."""


# ── the forbidden set (docs/04-tools.md §7) ─────────────────────────────
#
# Checked when a verb is LOADED and again before it EXECUTES, so a learned
# verb cannot slip through by being written to disk after startup.

FORBIDDEN_PATH_WRITES = (
    "/etc/hermesos",
    "/var/log/hermesos",
    "/usr/lib/hermesos",
    "/etc/sudoers",
    "/etc/sudoers.d",
    "/etc/shadow",
    "/boot",
)

FORBIDDEN_BINARIES = {
    "sudo", "su", "pkexec", "doas",          # privilege escalation
    "dd", "mkfs", "wipefs", "shred",          # raw device writes
    "visudo", "usermod", "useradd", "groupmod",
    "chpasswd", "passwd",
    "curl", "wget",                           # remote fetch → execute
    "bash", "sh", "zsh", "dash", "eval", "source",
    "python", "python3", "perl", "ruby", "node",
}

# Substrings that indicate someone tried to smuggle a shell in.
SHELL_METACHARS = re.compile(r"[;&|`$><\n]|\$\(|\|\||&&")


def guard_command(argv: list[str], *, where: str) -> None:
    """Refuse anything that looks like a shell, an escalation, or a raw write.

    `where` names the source for the error message ("verb pkg.install",
    "proposed verb fan.set").
    """
    if not argv:
        raise VerbError(f"{where}: the command is empty.")

    for token in argv:
        if not isinstance(token, str):
            raise VerbError(f"{where}: command parts must all be text.")
        if SHELL_METACHARS.search(token):
            raise VerbError(
                f"{where}: contains a shell character ({token!r}). Commands "
                "run directly, never through a shell, so this can never work "
                "and usually means something is trying to smuggle in a second "
                "command."
            )

    binary = Path(argv[0]).name
    # Strip a version suffix: python3.11 → python3
    if binary in FORBIDDEN_BINARIES or re.sub(r"[\d.]+$", "", binary) in FORBIDDEN_BINARIES:
        raise VerbError(
            f"{where}: '{binary}' is on the permanent no-list. It could be "
            "used to give me more power than you granted, so no verb may "
            "call it — not even one you teach me."
        )

    joined = " ".join(argv)
    for path in FORBIDDEN_PATH_WRITES:
        if path in joined:
            raise VerbError(
                f"{where}: touches {path}, which is permanently off limits. "
                "That path controls what I'm allowed to do, or records what "
                "I've done."
            )

    if "u+s" in joined or "4755" in joined or "+s" in joined.split():
        raise VerbError(f"{where}: sets a setuid bit, which grants permanent privilege.")


# ── the verb ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Verb:
    name: str
    summary: str
    risk: str
    explain: str
    execute: list[str]
    args: dict[str, ArgSpec] = field(default_factory=dict)
    dry_run: list[str] | None = None
    snapshot_before: bool = False
    parse_dry_run: str | None = None
    origin: str = "shipped"          # or "learned"
    confirm_word: str | None = None
    consequence: str | None = None   # critical verbs only

    @property
    def needs_approval(self) -> bool:
        return self.risk in ("medium", "high", "critical")

    @property
    def needs_typed_confirm(self) -> bool:
        return self.risk in ("high", "critical")


PLACEHOLDER = re.compile(r"^\{(\w+)\}$")


def _parse_args(raw: dict, verb_name: str) -> dict[str, ArgSpec]:
    out: dict[str, ArgSpec] = {}
    for key, spec in (raw or {}).items():
        if not isinstance(spec, dict) or "type" not in spec:
            raise VerbError(f"{verb_name}: argument '{key}' has no type.")
        out[key] = ArgSpec(
            type=spec["type"],
            required=spec.get("required", True),
            max_items=spec.get("max_items", 20),
            minimum=spec.get("min", 0),
            maximum=spec.get("max", 100),
            choices=tuple(spec.get("choices", ())),
            max_length=spec.get("max_length", 500),
        )
    return out


def load_verb(path: Path, *, origin: str = "shipped") -> Verb:
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise VerbError(f"{path.name}: not valid YAML ({exc}).") from exc

    name = data.get("verb")
    if not name:
        raise VerbError(f"{path.name}: missing 'verb' name.")

    risk = data.get("risk")
    if risk not in RISK_ORDER:
        raise VerbError(f"{name}: risk must be one of {', '.join(RISK_ORDER)}.")

    explain = (data.get("explain") or "").strip()
    if not explain:
        raise VerbError(
            f"{name}: has no 'explain' block. Every verb must carry its own "
            "plain-English description — the model is never allowed to write "
            "the warning the user reads."
        )

    execute = data.get("execute")
    if not isinstance(execute, list) or not execute:
        raise VerbError(
            f"{name}: 'execute' must be a list of command parts, never a "
            "single string. A string would imply a shell."
        )

    guard_command(execute, where=f"verb {name}")
    dry_run = data.get("dry_run")
    if dry_run is not None:
        if not isinstance(dry_run, list):
            raise VerbError(f"{name}: 'dry_run' must also be a list.")
        guard_command(dry_run, where=f"verb {name} (dry run)")

    args = _parse_args(data.get("args", {}), name)

    # Every {placeholder} in the command must correspond to a declared arg.
    for token in list(execute) + list(dry_run or []):
        m = PLACEHOLDER.match(token)
        if m and m.group(1) not in args:
            raise VerbError(
                f"{name}: command uses {{{m.group(1)}}} but no such argument "
                "is declared, so it could never be validated."
            )
        # A brace inside a larger token would mean string interpolation.
        if not m and ("{" in token or "}" in token):
            raise VerbError(
                f"{name}: {token!r} mixes a placeholder into a larger string. "
                "Placeholders must be a whole argv element on their own."
            )

    if risk in ("high", "critical") and not data.get("confirm_word"):
        raise VerbError(f"{name}: {risk} verbs must define a 'confirm_word'.")
    if risk == "critical" and not data.get("consequence"):
        raise VerbError(
            f"{name}: critical verbs must state a plain 'consequence' "
            "sentence — the user has to be told what is lost."
        )
    if risk in ("medium", "high", "critical") and not data.get("snapshot_before", True):
        raise VerbError(f"{name}: {risk} verbs cannot opt out of a snapshot.")

    return Verb(
        name=name,
        summary=data.get("summary", name),
        risk=risk,
        explain=explain,
        execute=execute,
        args=args,
        dry_run=dry_run,
        snapshot_before=data.get("snapshot_before", risk != "safe" and risk != "low"),
        parse_dry_run=data.get("parse_dry_run"),
        origin=origin,
        confirm_word=data.get("confirm_word"),
        consequence=data.get("consequence"),
    )


def load_all(shipped_dir: Path, learned_dir: Path | None = None) -> dict[str, Verb]:
    verbs: dict[str, Verb] = {}
    for path in sorted(shipped_dir.glob("*.yaml")):
        v = load_verb(path, origin="shipped")
        verbs[v.name] = v
    if learned_dir and learned_dir.is_dir():
        for path in sorted(learned_dir.glob("*.yaml")):
            v = load_verb(path, origin="learned")
            if v.name in verbs:
                raise VerbError(
                    f"{v.name}: a learned verb cannot replace the shipped one."
                )
            if v.risk in ("safe", "low"):
                raise VerbError(
                    f"{v.name}: learned verbs start at 'medium' risk minimum, "
                    "so the first use still asks you."
                )
            verbs[v.name] = v
    return verbs


def render_command(verb: Verb, template: list[str], values: dict) -> list[str]:
    """Substitute validated values into an argv template.

    A list-valued placeholder expands into multiple argv elements. Values are
    already validated; this never builds a string.
    """
    out: list[str] = []
    for token in template:
        m = PLACEHOLDER.match(token)
        if not m:
            out.append(token)
            continue
        val = values[m.group(1)]
        if isinstance(val, list):
            out.extend(str(v) for v in val)
        else:
            out.append(str(val))
    guard_command(out, where=f"verb {verb.name} (final)")
    return out


def quote_for_display(argv: list[str]) -> str:
    """Human-readable form, shown only when the user presses '?'."""
    return " ".join(shlex.quote(a) for a in argv)
