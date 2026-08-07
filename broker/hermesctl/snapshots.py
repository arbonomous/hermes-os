"""Restore points.

One interface, three backends. The executor never learns which one is in
use — it asks for a restore point and either gets one or refuses to run.

  btrfs     instant, copy-on-write. What the ISO installs.
  timeshift slower, used when converting an existing ext4 machine.
  none      no snapshots possible. The executor treats this as fatal for
            any verb that declares snapshot_before.

Honest limitation: a restore point covers the system, not $HOME. Rolling
back never touches the user's own files — that is a deliberate choice, and
docs/02-safety-model.md says so in plain language.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class SnapshotError(Exception):
    """A restore point could not be made or restored. Message is user-facing."""


@dataclass(frozen=True)
class Snapshot:
    name: str
    backend: str
    created: str
    label: str = ""

    @property
    def friendly(self) -> str:
        dt = datetime.fromisoformat(self.created.replace("Z", "+00:00")).astimezone()
        when = dt.strftime("%-d %b at %-I:%M%p").replace("AM", "am").replace("PM", "pm")
        return f"{self.label or self.name} — {when}"


def _now_name(prefix: str = "before") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _run(argv: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a helper. No shell, ever — same rule as the executor."""
    return subprocess.run(
        argv, shell=False, capture_output=True, text=True, timeout=timeout, check=False
    )


class SnapshotBackend:
    name = "abstract"

    def available(self) -> bool:
        raise NotImplementedError

    def create(self, label: str) -> Snapshot:
        raise NotImplementedError

    def list(self) -> list[Snapshot]:
        raise NotImplementedError

    def restore(self, name: str) -> str:
        raise NotImplementedError


class BtrfsBackend(SnapshotBackend):
    """Copy-on-write subvolume snapshots. Effectively instant."""

    name = "btrfs"

    def __init__(self, root: str = "/", store: str = "/.snapshots"):
        self.root = Path(root)
        self.store = Path(store)

    def available(self) -> bool:
        if not shutil.which("btrfs"):
            return False
        r = _run(["/usr/bin/findmnt", "-no", "FSTYPE", str(self.root)], timeout=10)
        return r.returncode == 0 and r.stdout.strip() == "btrfs"

    def create(self, label: str) -> Snapshot:
        name = _now_name()
        target = self.store / name
        r = _run(["/usr/bin/btrfs", "subvolume", "snapshot", "-r",
                  str(self.root), str(target)])
        if r.returncode != 0:
            raise SnapshotError(
                "I couldn't make a restore point, so I've stopped before "
                "changing anything.\n\n"
                f"The disk tool said: {r.stderr.strip() or 'no reason given'}"
            )
        return Snapshot(name=name, backend=self.name, created=_utcnow(), label=label)

    def list(self) -> list[Snapshot]:
        if not self.store.is_dir():
            return []
        out = []
        for p in sorted(self.store.iterdir(), reverse=True):
            if p.is_dir():
                ts = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
                out.append(Snapshot(
                    name=p.name, backend=self.name,
                    created=ts.isoformat(timespec="seconds").replace("+00:00", "Z"),
                ))
        return out

    def restore(self, name: str) -> str:
        target = self.store / name
        if not target.is_dir():
            raise SnapshotError(f"I can't find a restore point called {name}.")
        r = _run(["/usr/bin/hermesos-rollback", str(target)], timeout=300)
        if r.returncode != 0:
            raise SnapshotError(
                "The rollback didn't complete.\n\n"
                f"{r.stderr.strip() or 'No reason given.'}\n\n"
                "Your computer has not been changed. Restart and pick the "
                "previous restore point from the boot menu if it won't start "
                "normally."
            )
        return "Restored. The change takes effect after a restart."


class TimeshiftBackend(SnapshotBackend):
    """Slower rsync snapshots for converted ext4 machines."""

    name = "timeshift"

    def available(self) -> bool:
        return shutil.which("timeshift") is not None

    def create(self, label: str) -> Snapshot:
        name = _now_name()
        r = _run(["/usr/bin/timeshift", "--create", "--comments", label,
                  "--tags", "O", "--scripted"], timeout=900)
        if r.returncode != 0:
            raise SnapshotError(
                "I couldn't make a restore point, so I've stopped before "
                "changing anything.\n\n"
                f"Timeshift said: {r.stderr.strip() or 'no reason given'}"
            )
        return Snapshot(name=name, backend=self.name, created=_utcnow(), label=label)

    def list(self) -> list[Snapshot]:
        r = _run(["/usr/bin/timeshift", "--list", "--scripted"], timeout=60)
        if r.returncode != 0:
            return []
        out = []
        for line in r.stdout.splitlines():
            parts = line.split()
            # Timeshift list rows start with an index then a timestamp.
            if len(parts) >= 3 and parts[0].rstrip(">").isdigit():
                out.append(Snapshot(
                    name=parts[1], backend=self.name,
                    created=_utcnow(), label=" ".join(parts[2:])[:60],
                ))
        return out

    def restore(self, name: str) -> str:
        r = _run(["/usr/bin/timeshift", "--restore", "--snapshot", name,
                  "--scripted"], timeout=1800)
        if r.returncode != 0:
            raise SnapshotError(
                "The rollback didn't complete.\n\n"
                f"{r.stderr.strip() or 'No reason given.'}"
            )
        return "Restored. The change takes effect after a restart."


class NoSnapshots(SnapshotBackend):
    """No backend. Any verb needing a restore point must refuse to run."""

    name = "none"

    def available(self) -> bool:
        return True

    def create(self, label: str) -> Snapshot:
        raise SnapshotError(
            "This computer can't make restore points, so I won't make a "
            "change I couldn't undo.\n\n"
            "If you want to go ahead anyway, type !shell and do it yourself "
            "— but please back up anything important first."
        )

    def list(self) -> list[Snapshot]:
        return []

    def restore(self, name: str) -> str:
        raise SnapshotError("There are no restore points on this computer.")


def detect(prefer: str | None = None) -> SnapshotBackend:
    """Pick a backend. btrfs wins; timeshift is the fallback; none is last."""
    candidates: list[SnapshotBackend] = [BtrfsBackend(), TimeshiftBackend()]
    if prefer:
        for c in candidates:
            if c.name == prefer:
                return c if c.available() else NoSnapshots()
    for c in candidates:
        if c.available():
            return c
    return NoSnapshots()
