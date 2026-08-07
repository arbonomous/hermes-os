# integration/

Tests that need a **real Linux kernel**. Unit tests use doubles; these use
an actual btrfs filesystem, because a mocked snapshot proves nothing about
whether rollback works.

| File | What it does |
|---|---|
| `lima-hermesos.yaml` | Ubuntu 24.04 VM definition (free, open-source) |
| `test_btrfs_roundtrip.py` | Real create / list / restore against loopback btrfs |
| `run.sh` | Boots the VM if needed, runs the test inside it |

## Run it

```bash
./integration/run.sh
```

First run downloads an Ubuntu cloud image (~600 MB) and takes a few minutes.
After that the VM is cached and it's quick.

## What it proves that unit tests can't

- `BtrfsBackend.available()` returns True on genuine btrfs
- `create()` produces a real, **read-only** subvolume
- The snapshot keeps the old contents after the live filesystem changes
- Two snapshots are independent point-in-time captures
- A restored tree has the old contents and is writable again
- Snapshotting 200 MB takes **under two seconds** — the copy-on-write claim
  the whole undo promise rests on

## Safety

Everything happens on a 1 GB **loopback file** inside the VM. The host is
never touched, and the test refuses to run at all unless it finds Linux,
root, and btrfs tooling — running it on a Mac prints `SKIPPED` and exits 0.

## Why Lima

Free, open-source, no licence. Docker Desktop is licensed for larger
companies, and containers share the host kernel anyway — which on macOS
means no btrfs. Lima gives a real kernel.

## Cleaning up

```bash
limactl stop hermesos && limactl delete hermesos
```
