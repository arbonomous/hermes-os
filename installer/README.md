# installer/

| File | Status |
|---|---|
| `install.sh` | Preflight + plan screen **working**; install steps are a stub |
| `test-install.sh` | 21 tests, all passing, no root required |

## Run the tests

```bash
./test-install.sh
```

Uses `HERMESOS_FAKE_*` environment seams to simulate any machine — wrong
distro, too little RAM, ext4 vs btrfs, already-installed — so the whole
refusal matrix from `docs/06-install.md` §7 is testable on a laptop with no
VM and no root.

## Try it

```bash
./install.sh --preflight    # check this machine, no root needed
./install.sh --dry-run      # print the plan, change nothing
```

## What is NOT built yet

Everything after the plan screen. `main()` stops at a stub. The next commit
on this branch adds: package installation, the `hermes` user, broker install,
login-shell swap, and `hermesos-uninstall`.

Deliberate order — the refusal paths and the consent screen are what protect
a beginner, so they are written and tested before anything that mutates a
system.
