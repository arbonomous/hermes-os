# HermesOS — Installation

Two paths in. Both must be survivable by someone who has never opened a
terminal.

| Path | Who it's for | Undo quality |
|---|---|---|
| **A — The ISO** | New machine, or a disk you're happy to erase | Full (btrfs) |
| **B — The converter** | An Ubuntu Server 24.04 box that already exists | Degraded (see §4) |

Path A is the supported one. Path B exists because most people trying this
will have a spare VM or an old laptop with Ubuntu already on it, and telling
them to reinstall is how you lose them.

---

## 1. Path A — the ISO

### 1.1 What the user does

1. Download `hermesos-0.1-amd64.iso`
2. Write it to a USB stick (we link one tool per OS, with pictures)
3. Boot from it
4. Answer **four** questions
5. Wait
6. The machine reboots into the first-boot wizard (`07-first-boot.md`)

Four questions, not forty:

```
  1.  Which disk should HermesOS use?
        ▸ 476 GB SSD  (Samsung 860 EVO)  — empty
          931 GB HDD  (WD Blue)          — has Windows on it

      I'll erase everything on the disk you pick.

  2.  Erase it and continue?
        Type  erase  to confirm.

  3.  Should I lock the disk with a password?
        ▸ No — simpler
          Yes — for laptops you carry

  4.  Connect to wifi?  (or skip — you can do it later)
```

Everything else — partitioning, filesystem, bootloader, users, packages — is
decided for them. There is no "advanced" branch on this path.

### 1.2 What the ISO does, in order

```
  1. Detect firmware (UEFI vs BIOS) and disk
  2. Partition:
       ESP        1 GB    fat32   /boot/efi
       boot       2 GB    ext4    /boot
       root       rest    btrfs   subvols: @ @home @snapshots @var-log
  3. Debootstrap Ubuntu Server 24.04 minimal
  4. Install: linux-generic, grub, systemd, network stack, btrfs-progs
  5. Install: ollama, hermes-agent (pinned versions, from the ISO — no network needed)
  6. Install: hermesos packages (broker, snapshotd, shell, firstboot)
  7. Write GRUB entries, including "previous restore point"
  8. Take snapshot: "factory"
  9. Touch /etc/hermesos/.setup-pending
 10. Reboot
```

**Everything in steps 4-6 is on the ISO.** A HermesOS machine can be installed
with no internet at all. Only the model download needs a connection, and that
is deferrable (`07-first-boot.md` §5, "Skip for now").

### 1.3 Why btrfs, non-negotiably

Undo is the feature that lets a beginner experiment without fear. On btrfs a
snapshot is instant and costs nothing until data diverges; rollback is a
subvolume swap. That's what makes "undo that" honest rather than a 20-minute
file copy that might fail halfway.

Subvolume layout is chosen so a rollback does the right thing:

| Subvol | Mount | Rolled back by `undo`? |
|---|---|---|
| `@` | `/` | **Yes** — system state |
| `@home` | `/home` | **No** — the user's own files are never reverted |
| `@snapshots` | `/.snapshots` | No — would eat itself |
| `@var-log` | `/var/log` | No — the audit must survive a rollback |

That third and fourth row matter. If `undo` reverted the audit log, the system
could erase evidence of what it did. If it reverted `/home`, a user rolling
back a bad package install would lose an afternoon's work and never trust it
again.

### 1.4 The recovery entry

GRUB gets three entries, in this order:

```
  HermesOS
  HermesOS — previous restore point
  HermesOS — recovery (plain terminal)
```

The second is regenerated on every snapshot. This is the floor of the safety
model: if the agent, an update, or the user ever renders the system unbootable,
recovery is *pressing the down arrow*, not finding a forum post.

---

## 2. Path B — the converter

For a machine already running Ubuntu Server 24.04.

```bash
curl -fsSL https://hermesos.org/install.sh | sudo bash
```

I dislike `curl | bash` and we ship it anyway, because the alternative for a
beginner is worse. Mitigations:

- The script is **short, single-file, and readable** — we link the source next
  to the command and it fits on two screens
- It **prints a plan and waits** before touching anything (§3)
- It is **idempotent** — safe to run twice
- A SHA-256 is published; the docs show how to check it, without insisting
- `--dry-run` prints every action and changes nothing

### 2.1 What it will not do

The script **refuses to run** if:

| Condition | Why |
|---|---|
| Not Ubuntu 24.04 | Untested; a beginner can't recover from a half-conversion |
| Less than 15 GB free | The model alone needs 5 GB |
| Less than 8 GB RAM | Even the small model thrashes below this |
| Already converted | Points at `hermesos-update` instead |
| Not root | Explains `sudo`, exits |

Each refusal is a plain sentence with a next step, never a bare exit code.

---

## 3. The plan screen

Both paths show this before any change. It is the installer's approval card.

```
  ┌──────────────────────────────────────────────────────────┐
  │  Here's what I'm about to do to this computer.           │
  │                                                          │
  │  I WILL ADD                                              │
  │    · Ollama — runs the AI locally            (~120 MB)   │
  │    · Hermes Agent — the assistant itself      (~90 MB)   │
  │    · HermesOS safety tools                    (~15 MB)   │
  │    · btrfs tools, for restore points          (~10 MB)   │
  │                                                          │
  │  I WILL CHANGE                                           │
  │    · Your login: you'll land in a conversation           │
  │      instead of a command prompt.                        │
  │      (Type !shell any time for the normal terminal.)     │
  │    · Add one system user called "hermes", with no        │
  │      admin rights.                                       │
  │                                                          │
  │  I WILL NOT                                              │
  │    · Touch any of your files                             │
  │    · Remove or upgrade anything you already have         │
  │    · Change your password or your account                │
  │    · Send anything over the internet except the          │
  │      downloads listed above                              │
  │                                                          │
  │  IF YOU CHANGE YOUR MIND                                 │
  │    Run  hermesos-uninstall  and everything above is      │
  │    reversed. Your files are untouched either way.        │
  │                                                          │
  │  About 4 minutes, plus the model download later.         │
  │                                                          │
  │  Type  yes  to continue, or press Ctrl-C to stop.        │
  └──────────────────────────────────────────────────────────┘
```

**The "I WILL NOT" block is the most important thing on this screen.** A
beginner's real question isn't "what does this add" — it's *"will this break
what I already have?"* Answering it unprompted, in the negative, specifically,
is what earns the `yes`.

---

## 4. Honest limits of Path B

An existing ext4 root **cannot** be converted to btrfs safely in place. So on
Path B, undo is worse, and we say so during install rather than letting the
user discover it during a crisis:

```
  One thing worth knowing.

  Your disk uses a format called ext4. I can still make
  restore points, using a tool called Timeshift — but they
  take a few minutes instead of a few seconds, and they use
  real disk space.

  On a fresh install I'd use btrfs, where restore points are
  instant and nearly free.

  This is fine. It just means "undo that" is slower here.
  If you ever reinstall from the HermesOS disc, you'll get
  the fast version.
```

| | Path A (btrfs) | Path B (ext4 + Timeshift) |
|---|---|---|
| Snapshot time | < 1 s | 2-10 min |
| Space cost | Near zero | Full copy of changed files |
| Pre-action auto-snapshot | Always | **Daily only** — too slow per-action |
| Rollback | Subvolume swap, seconds | File restore, minutes |
| GRUB restore entry | Yes | No |

That "daily only" row is a genuine safety regression, not a performance note.
On Path B, `undo that` after a bad install may cost the user a day of system
changes rather than five minutes. The installer says this in plain words, and
`hermes` repeats it the first time a medium-risk card appears.

---

## 5. Uninstall

Ships from day one. A system you cannot leave is a system you cannot trust.

```bash
sudo hermesos-uninstall
```

Removes the HermesOS packages, restores the login shell to bash, and asks
separately about Ollama, the downloaded models, the audit log, and any
abilities that were taught. Nothing in `/home` is touched. The final message
names exactly what was removed and what was kept.

---

## 6. What the installer never does

| Never | Why |
|---|---|
| Auto-reboot without asking | Someone may have unsaved work |
| Add a third-party apt repo | Unreviewed code path |
| Enable a network listener | Ollama binds `127.0.0.1` only; gateway is off |
| Send telemetry | There is none |
| Create an account anywhere | Local-first means no account |
| Modify existing users' dotfiles | Only appends to the login shell entry, reversibly |
| Continue past a failed step | Stops, explains, offers rollback |

---

## 7. Build & test gate

`installer/` changes must pass a full clean-VM run before merging to
`develop` — see `CONTRIBUTING.md`. The matrix:

| Case | Expect |
|---|---|
| Fresh 24.04 VM, ext4 | Converts, warns about degraded undo |
| Fresh 24.04 VM, btrfs root | Converts, full undo |
| 22.04 VM | Refuses, explains |
| 4 GB RAM VM | Refuses, explains |
| Run twice | Second run is a no-op |
| `--dry-run` | Zero changes on disk, full plan printed |
| Ctrl-C at the plan screen | Zero changes on disk |
| Network cut mid-install | Stops cleanly, resumable |
| `hermesos-uninstall` after | Login shell restored, `/home` untouched |
