#!/usr/bin/env python3
"""Real btrfs round trip. NOT a unit test — this needs a Linux VM.

    sudo ./integration/test_btrfs_roundtrip.py

Runs against a loopback btrfs filesystem, so it never touches the host's
real root. Proves the thing doubles cannot: that BtrfsBackend actually
creates, lists, and restores from a genuine btrfs subvolume.

Skips (exit 0) unless it finds Linux + btrfs tooling + root, so it stays
harmless if someone runs it on a laptop by mistake.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "broker"))

PASS, FAIL = [], []


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{f' — {detail}' if detail else ''}")


def sh(*argv, check_rc=True):
    r = subprocess.run(argv, capture_output=True, text=True)
    if check_rc and r.returncode != 0:
        raise RuntimeError(f"{' '.join(argv)} failed:\n{r.stderr}")
    return r


def preflight() -> str | None:
    if sys.platform != "linux":
        return f"not Linux (this is {sys.platform})"
    if os.geteuid() != 0:
        return "needs root (loopback mount + subvolumes)"
    for tool in ("mkfs.btrfs", "btrfs", "losetup", "mount"):
        if not shutil.which(tool):
            return f"{tool} not installed"
    return None


def main() -> int:
    why = preflight()
    if why:
        print(f"\nSKIPPED — {why}")
        print("This test needs a Linux VM with btrfs-progs. See integration/README.md")
        return 0

    from hermesctl.snapshots import BtrfsBackend, SnapshotError

    work = Path(tempfile.mkdtemp(prefix="hermesos-btrfs-"))
    img = work / "disk.img"
    mnt = work / "mnt"
    mnt.mkdir()
    loop = None

    try:
        print("\n[setup] building a 4 GB loopback btrfs filesystem")
        # 1 GB is too small: scene 8 copies the snapshot into a writable tree
        # and scene 9 writes 200 MB, which on real (near-full) btrfs flips the
        # mount read-only and breaks the test. 4 GB leaves headroom.
        sh("truncate", "-s", "4G", str(img))
        loop = sh("losetup", "--find", "--show", str(img)).stdout.strip()
        sh("mkfs.btrfs", "-q", loop)
        sh("mount", loop, str(mnt))
        print(f"  loop device: {loop}")
        print(f"  mounted at:  {mnt}")

        # A subvolume standing in for the root filesystem.
        rootvol = mnt / "@"
        sh("btrfs", "subvolume", "create", str(rootvol))
        (rootvol / "etc").mkdir()
        (rootvol / "etc" / "hostname").write_text("before-change\n")
        store = mnt / ".snapshots"
        store.mkdir()

        be = BtrfsBackend(root=str(rootvol), store=str(store))

        print("\n[1] backend detects real btrfs")
        check("available() is True on btrfs", be.available())

        print("\n[2] create a restore point")
        snap = be.create(label="Install vlc")
        check("create() returned a Snapshot", snap is not None)
        check("snapshot directory exists", (store / snap.name).is_dir(),
              str(store / snap.name))
        check("snapshot is a real subvolume",
              sh("btrfs", "subvolume", "show", str(store / snap.name),
                 check_rc=False).returncode == 0)
        check("snapshot is read-only",
              "ro=true" in sh("btrfs", "property", "get",
                              str(store / snap.name)).stdout)

        print("\n[3] the snapshot captured the old contents")
        captured = (store / snap.name / "etc" / "hostname").read_text()
        check("file preserved inside snapshot", captured == "before-change\n",
              repr(captured))

        print("\n[4] change the live filesystem")
        (rootvol / "etc" / "hostname").write_text("after-change\n")
        (rootvol / "etc" / "new-file.conf").write_text("added later\n")
        check("live file changed",
              (rootvol / "etc" / "hostname").read_text() == "after-change\n")
        check("snapshot did NOT change",
              (store / snap.name / "etc" / "hostname").read_text() == "before-change\n")
        check("new file absent from snapshot",
              not (store / snap.name / "etc" / "new-file.conf").exists())

        print("\n[5] list() finds it")
        listed = be.list()
        check("list() returns the snapshot", any(s.name == snap.name for s in listed),
              f"{len(listed)} found")
        check("friendly name is human-readable",
              "—" in listed[0].friendly, listed[0].friendly)

        print("\n[6] a second restore point is independent")
        # rootvol is still writable — `btrfs subvolume snapshot -r` marks the
        # NEW snapshot read-only, never the source.
        snap2 = be.create(label="Remove gimp")
        check("two distinct snapshots", snap2.name != snap.name)
        check("second captured the NEW state",
              (store / snap2.name / "etc" / "hostname").read_text() == "after-change\n")
        check("first still holds the OLD state",
              (store / snap.name / "etc" / "hostname").read_text() == "before-change\n")

        print("\n[7] restore refuses a name that doesn't exist")
        try:
            be.restore("no-such-snapshot")
            check("unknown snapshot refused", False, "no exception raised")
        except SnapshotError as exc:
            check("unknown snapshot refused", "can't find" in str(exc), str(exc)[:60])

        print("\n[8] rollback semantics (manual subvolume swap)")
        # hermesos-rollback isn't installed here, so we prove the underlying
        # operation the helper performs: swap the live subvolume for a
        # writable copy of the snapshot.
        sh("btrfs", "subvolume", "snapshot", str(store / snap.name),
           str(mnt / "@restored"))
        restored = (mnt / "@restored" / "etc" / "hostname").read_text()
        check("restored tree has the old contents", restored == "before-change\n",
              repr(restored))
        check("restored tree is writable",
              "ro=true" not in sh("btrfs", "property", "get",
                                  str(mnt / "@restored")).stdout)

        print("\n[9] two snapshots in the same wall-clock second (name collision)")
        # Regression: _now_name() used second precision. Two quick snapshots
        # collided on name, hit an existing read-only subvolume, and btrfs
        # misreported "Read-only file system". Now names carry microseconds.
        from hermesctl.snapshots import _now_name
        n_a, n_b = _now_name(), _now_name()
        check("microsecond names never collide", n_a != n_b)
        s_fast1 = be.create(label="quick one")
        s_fast2 = be.create(label="quick two")
        check("two rapid snapshots both succeed",
              s_fast1.name != s_fast2.name)
        check("rapid snapshots are distinct subvolumes",
              (store / s_fast1.name).is_dir() and (store / s_fast2.name).is_dir())

        print("\n[10] snapshot creation is fast (CoW, not a copy)")
        import time
        big = rootvol / "big.bin"
        big.write_bytes(b"\0" * (200 * 1024 * 1024))   # 200 MB
        sh("sync")
        t0 = time.monotonic()
        snap3 = be.create(label="after big file")
        elapsed = time.monotonic() - t0
        check("200 MB snapshot took under 2s", elapsed < 2.0, f"{elapsed:.3f}s")
        check("big file visible in snapshot",
              (store / snap3.name / "big.bin").stat().st_size == 200 * 1024 * 1024)

    finally:
        print("\n[teardown]")
        subprocess.run(["umount", str(mnt)], capture_output=True)
        if loop:
            subprocess.run(["losetup", "-d", loop], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)
        print("  loopback removed, host untouched")

    print(f"\n{'=' * 50}\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED: " + "; ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
