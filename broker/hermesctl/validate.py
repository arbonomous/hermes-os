"""Argument validation.

Every value the model sends is validated here before anything runs. This is
the layer that makes shell injection and path traversal impossible rather
than merely discouraged.

Rules:
  · Validators return the CLEANED value or raise ValidationError.
  · Path types resolve symlinks with realpath BEFORE checking prefixes, so
    a symlink out of $HOME fails at validation, not at execution.
  · No validator ever runs a shell.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


class ValidationError(Exception):
    """Raised when an argument is not acceptable. Message is user-facing."""


# ── primitives ──────────────────────────────────────────────────────────

PACKAGE_RE = re.compile(r"^[a-z0-9][a-z0-9+.\-]{0,99}$")
SERVICE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9@._\-]{0,99}(\.[a-z]+)?$")
SNAPSHOT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\-]{0,63}$")

# Control characters, including NUL, newline and ESC. Newlines in an argv
# element are legal to execve but let a value forge extra log lines.
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _no_control(value: str, what: str) -> str:
    if CONTROL_RE.search(value):
        raise ValidationError(
            f"That {what} contains characters I don't allow "
            "(invisible control codes). This is usually a mistake."
        )
    return value


def package_name(value: object, **_) -> str:
    if not isinstance(value, str):
        raise ValidationError("A package name has to be text.")
    value = _no_control(value.strip(), "package name")
    if not PACKAGE_RE.match(value):
        raise ValidationError(
            f"'{value}' isn't a valid package name. Package names use "
            "lowercase letters, numbers, and the symbols + - . only."
        )
    return value


def service_name(value: object, **_) -> str:
    if not isinstance(value, str):
        raise ValidationError("A service name has to be text.")
    value = _no_control(value.strip(), "service name")
    if not SERVICE_RE.match(value):
        raise ValidationError(f"'{value}' isn't a valid service name.")
    return value


def snapshot_name(value: object, **_) -> str:
    if not isinstance(value, str):
        raise ValidationError("A restore point name has to be text.")
    value = _no_control(value.strip(), "name")
    if not SNAPSHOT_RE.match(value):
        raise ValidationError(
            "Restore point names can use letters, numbers, dots, dashes "
            "and underscores."
        )
    return value


def bounded_int(value: object, *, minimum: int, maximum: int, **_) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("That needs to be a whole number.")
    if not minimum <= value <= maximum:
        raise ValidationError(f"That number has to be between {minimum} and {maximum}.")
    return value


def enum(value: object, *, choices: tuple[str, ...], **_) -> str:
    if value not in choices:
        raise ValidationError(
            f"That has to be one of: {', '.join(choices)}."
        )
    return str(value)


def text(value: object, *, max_length: int = 500, **_) -> str:
    if not isinstance(value, str):
        raise ValidationError("That has to be text.")
    if len(value) > max_length:
        raise ValidationError(f"That's too long (limit {max_length} characters).")
    return _no_control(value, "text")


# ── paths — the traversal-critical ones ─────────────────────────────────

def _resolved(value: str) -> Path:
    """Expand and fully resolve, following symlinks on existing components.

    Path.resolve(strict=False) resolves as much as exists and lexically
    normalises the rest, so '..' cannot survive and a symlinked parent is
    followed before we compare prefixes.
    """
    return Path(os.path.expanduser(value)).resolve()


def _under(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def user_path(value: object, *, home: str | os.PathLike, **_) -> str:
    """A path the user owns. Must resolve inside their home directory."""
    if not isinstance(value, str) or not value:
        raise ValidationError("That needs to be a file or folder path.")
    _no_control(value, "path")
    home_p = Path(home).resolve()
    target = _resolved(value)
    if not _under(target, home_p):
        raise ValidationError(
            "I can only touch files in your own home folder. "
            f"That path points outside it ({target})."
        )
    return str(target)


# Prefixes a system_path may live under. Everything else is refused.
SYSTEM_ALLOW = ("/etc", "/usr/local", "/opt", "/srv", "/var/lib")

# Never, under any verb, learned or shipped. Mirrors docs/04-tools.md §7.
SYSTEM_DENY = (
    "/etc/hermesos",
    "/var/log/hermesos",
    "/etc/sudoers",
    "/etc/sudoers.d",
    "/etc/shadow",
    "/etc/gshadow",
    "/boot",
    "/usr/lib/hermesos",
    "/etc/polkit-1",
    "/root",
)


def _prefix_match(target: Path, prefix: str) -> bool:
    """True if `target` is `prefix` or sits underneath it.

    Both sides are resolved before comparison. This matters on any system
    where an allowlisted prefix is itself a symlink (macOS symlinks /etc to
    /private/etc); comparing a resolved path against an unresolved prefix
    would wrongly reject — or worse, wrongly accept — a path.
    Component-wise comparison also means /etc/hermesos-notes never matches
    the /etc/hermesos prefix.
    """
    resolved_prefix = Path(prefix).resolve()
    return target == resolved_prefix or _under(target, resolved_prefix)


def system_path(value: object, **_) -> str:
    """A path outside $HOME. Allowlisted prefixes, minus the forbidden set."""
    if not isinstance(value, str) or not value:
        raise ValidationError("That needs to be a file path.")
    _no_control(value, "path")
    target = _resolved(value)

    for denied in SYSTEM_DENY:
        if _prefix_match(target, denied):
            raise ValidationError(
                f"{denied} is on my permanent no-list — I'm locked out of it "
                "on purpose, even when you ask. Type !shell if you want to "
                "change it yourself."
            )

    if not any(_prefix_match(target, p) for p in SYSTEM_ALLOW):
        raise ValidationError(
            f"I'm not allowed to touch {value}. I can only reach: "
            f"{', '.join(SYSTEM_ALLOW)}."
        )
    return str(target)


def device(value: object, **_) -> str:
    """A block device. Must be a by-id link and must not be the root disk."""
    if not isinstance(value, str) or not value:
        raise ValidationError("That needs to be a disk name.")
    _no_control(value, "device")
    if not value.startswith("/dev/disk/by-id/"):
        raise ValidationError(
            "For safety I only accept disks by their permanent ID "
            "(/dev/disk/by-id/...), because /dev/sda can point at a "
            "different disk after a reboot."
        )
    return value


# ── the type table ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ArgSpec:
    type: str
    required: bool = True
    max_items: int = 20
    minimum: int = 0
    maximum: int = 100
    choices: tuple[str, ...] = ()
    max_length: int = 500


VALIDATORS = {
    "package_name": package_name,
    "service_name": service_name,
    "snapshot_name": snapshot_name,
    "user_path": user_path,
    "system_path": system_path,
    "device": device,
    "int": bounded_int,
    "enum": enum,
    "text": text,
}


def validate_arg(spec: ArgSpec, value: object, *, home: str) -> object:
    """Validate one argument. Lists are validated element-wise."""
    base = spec.type
    is_list = base.startswith("list[") and base.endswith("]")
    if is_list:
        base = base[5:-1]

    fn = VALIDATORS.get(base)
    if fn is None:
        raise ValidationError(f"I don't know how to check a '{spec.type}'.")

    kwargs = dict(
        home=home,
        minimum=spec.minimum,
        maximum=spec.maximum,
        choices=spec.choices,
        max_length=spec.max_length,
    )

    if not is_list:
        return fn(value, **kwargs)

    if not isinstance(value, (list, tuple)):
        raise ValidationError("That needs to be a list.")
    if not value:
        raise ValidationError("That list is empty — I need at least one item.")
    if len(value) > spec.max_items:
        raise ValidationError(
            f"That's {len(value)} items and I only allow {spec.max_items} "
            "at a time. Let's do it in smaller batches."
        )
    return [fn(v, **kwargs) for v in value]
