"""Tests for the snapshot backends and helpers."""
from __future__ import annotations

import pytest

from hermesctl.snapshots import (
    BtrfsBackend,
    NoSnapshots,
    SnapshotBackend,
    SnapshotError,
    _now_name,
)
from hermesctl.verbs import load_all

VERBS = VERBS = None  # placeholder; real path set below
from pathlib import Path
VERBS = Path(__file__).resolve().parents[2] / "verbs.d"


def test_now_name_has_microsecond_precision():
    # Regression guard: second-precision names collide when two snapshots
    # land in the same wall-clock second, which made btrfs (mis)report
    # "Read-only file system". Caught on a real VM, not in unit tests.
    a = _now_name()
    b = _now_name()
    assert a != b
    assert len(a.split("-")[-1]) == 6  # %f -> 6 digits


def test_now_name_is_unique_across_many_calls():
    names = [_now_name() for _ in range(1000)]
    assert len(set(names)) == len(names)


def test_no_snapshots_is_the_refusal_backend():
    """NoSnapshots exists so the executor can refuse snapshot-needing verbs.
    `available()` is intentionally True; the refusal lives in create()."""
    ns = NoSnapshots()
    assert ns.available()
    with pytest.raises(SnapshotError, match="can't make restore points"):
        ns.create("x")
    assert ns.list() == []
    with pytest.raises(SnapshotError, match="no restore points"):
        ns.restore("x")


def test_btrfs_create_refuses_existing_subvolume(tmp_path):
    """A name collision must not produce btrfs's misleading 'Read-only'.

    Reproduces the real bug path without a kernel: make create() compute a
    target whose directory already exists (as a second snapshot in the same
    wall-clock second would), and confirm the guard refuses with the true
    cause before any btrfs call. No /usr/bin/btrfs needed.
    """
    import hermesctl.snapshots as S

    be = BtrfsBackend(root=str(tmp_path), store=str(tmp_path / ".snapshots"))
    be.available = lambda: True  # pretend btrfs is present

    # Force a deterministic name, then pre-create that exact target so the
    # guard's target.exists() check fires.
    fixed = "before-collide"
    S._now_name = lambda prefix="before": fixed
    (be.store / fixed).mkdir(parents=True, exist_ok=True)

    # No btrfs call must be attempted — assert by making _run fatal if reached.
    S._run = lambda *a, **k: (_ for _ in ()).throw(AssertionError("btrfs was called"))

    with pytest.raises(SnapshotError, match="already exists"):
        be.create("x")
