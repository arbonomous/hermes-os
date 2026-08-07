# HermesOS — The Tool Surface

Every privileged thing Hermes can do, and the wrapper that makes it safe.

**Reading this document:** each verb is a file in `/etc/hermesos/verbs.d/`.
The tables below are the shipped set for v0.1 — roughly 40 verbs. Anything
not here either (a) needs teaching via §5 of the safety model, or (b) is in
the forbidden set and can never exist.

---

## 1. How a verb is defined

```yaml
verb: pkg.install
summary: "Install an application from Ubuntu's official catalogue"
args:
  names:
    type: list[package_name]      # regex-validated, max 20 items
risk: medium
snapshot_before: true
dry_run:  ["apt-get", "install", "--simulate", "{names}"]
execute:  ["apt-get", "install", "-y", "{names}"]
parse_dry_run: apt_simulate       # named parser → "4 new, 0 removed, 18 MB"
explain: |
  I'll install {names} from Ubuntu's official software catalogue.
  This adds new programs. It doesn't remove anything.
```

Five properties do all the safety work:

| Property | Guarantee |
|---|---|
| `execute` is an **argv array**, never a string | No shell. No `;`, `&&`, backticks, `$()`. Injection is not merely blocked — it is syntactically impossible |
| `args` are **typed** | `package_name` is `^[a-z0-9][a-z0-9+.-]*$`. A malformed arg fails before execution |
| `explain` is **authored by us**, not the model | A hallucinating model picks the verb; the *system* writes the warning |
| `parse_dry_run` produces **real numbers** | "WHAT CHANGES" comes from apt/systemd itself, not from a guess |
| `risk` + `snapshot_before` are **declared, not decided at runtime** | The model cannot downgrade its own risk tier |

### Argument types

| Type | Validation |
|---|---|
| `package_name` | `^[a-z0-9][a-z0-9+.-]{0,99}$`, must exist in apt cache |
| `service_name` | Must match an existing unit in `systemctl list-unit-files` |
| `user_path` | Must resolve inside `/home/<user>` after symlink resolution |
| `system_path` | Allowlisted prefixes only; never `/etc/hermesos`, `/var/log/hermesos` |
| `device` | Must be in `/dev/disk/by-id/`, must not be the root device |
| `enum[...]` | One of a fixed list |
| `int(min,max)` | Bounded integer |
| `text` | Length-capped, control characters stripped |

**Path traversal is closed at the type layer**, not by string inspection:
`user_path` resolves the real path via `realpath()` and re-checks the prefix.
`../../etc/shadow` fails validation, not execution.

---

## 2. Read-only verbs — `safe`, never ask

These need no approval, no snapshot, no card. They are how Hermes answers
questions. All are logged.

| Verb | What it answers |
|---|---|
| `sys.overview` | "what's on this computer?" — disk, memory, network, updates, restore points |
| `sys.hardware` | CPU, RAM, GPU, disks, battery |
| `sys.disk` | Usage per filesystem, biggest directories |
| `sys.memory` | Current usage, what's using it |
| `sys.uptime` | Boot time, load |
| `sys.temperature` | Thermal sensors, fan speeds |
| `pkg.search` | Find installable software |
| `pkg.list` | What's installed |
| `pkg.info` | Details of one package |
| `pkg.updates` | What updates are available (does **not** apply them) |
| `svc.status` | Is a service running |
| `svc.list` | What's running |
| `svc.logs` | Recent journal for one unit, translated |
| `net.status` | Connection, IP, wifi name, signal |
| `net.wifi.scan` | Visible networks |
| `net.test` | Can we reach the internet, DNS, latency |
| `file.list` | Directory contents under `$HOME` |
| `file.read` | Read a text file under `$HOME` |
| `file.search` | Find files by name/content under `$HOME` |
| `snapshot.list` | Restore points and their dates |
| `audit.read` | "what have you done today?" |
| `caps.list` | "what can you do?" — shipped vs learned abilities |

**Boundary:** `file.read` and `file.search` are `$HOME`-scoped. Reading
`/etc/shadow` isn't a policy decision, it's a type failure. Reading a system
config file is a separate `medium` verb (`sys.config.read`) so it produces a
card — because "show me your SSH keys" should not be silent.

---

## 3. Low-risk verbs — reversible, user-scoped, auto-approved

Logged, not carded. All confined to the user's own home.

| Verb | Risk | Notes |
|---|---|---|
| `file.write` | low | `$HOME` only; writes a `.bak` if overwriting |
| `file.mkdir` | low | `$HOME` only |
| `file.move` | low | `$HOME` only, both ends |
| `file.copy` | low | `$HOME` only |
| `ui.font-size` | low | Console font; instantly visible, instantly reversible |
| `ui.theme` | low | Colour scheme |
| `shell.alias` | low | Adds to the user's own rc file |
| `prefs.set` | low | HermesOS preferences (tips on/off, verbosity, approval mode↑ only) |

**`prefs.set` can only make approval mode stricter, never looser.** Loosening
is `high` and requires a card. The agent cannot quietly turn off its own
supervision.

**`file.delete` is deliberately NOT low.** It's `high` — see §5.

---

## 4. Medium-risk verbs — system-modifying, reversible, always ask

Card + snapshot before every one.

| Verb | What it does |
|---|---|
| `pkg.install` | Install from Ubuntu's catalogue |
| `pkg.update` | Refresh the package index (safe but slow, so it asks) |
| `pkg.upgrade` | Apply available updates |
| `svc.start` / `svc.stop` / `svc.restart` | Control a service |
| `svc.enable` / `svc.disable` | Start at boot or not |
| `net.wifi.connect` | Join a network |
| `net.wifi.forget` | Remove a saved network |
| `time.set-timezone` | Change time zone |
| `locale.set` | Change language/locale |
| `sys.config.read` | Read a file outside `$HOME` |
| `model.pull` | Download a different model |
| `model.switch` | Change the active model |
| `snapshot.create` | Make a restore point manually |
| `power.reboot` / `power.shutdown` | Restart or shut down (carded because unsaved work) |

**Why `pkg.update` asks even though it changes nothing:** it takes 30+ seconds
and touches the network. Surprise latency erodes trust as much as surprise
change. A card saying *"this takes about a minute"* is kinder than a silent pause.

---

## 5. High-risk verbs — hard to reverse, typed confirmation

Card + snapshot + the user must **type a word** shown on screen.

| Verb | Why it's high |
|---|---|
| `pkg.remove` | Can break dependent software |
| `pkg.autoremove` | Removes several things at once |
| `file.delete` | Data loss, even in `$HOME` |
| `file.chmod` / `file.chown` | Can lock the user out of their own files |
| `svc.mask` | Makes a service unstartable — confusing to diagnose later |
| `net.firewall.*` | Can cut remote access |
| `snapshot.restore` | Discards everything since the snapshot |
| `snapshot.prune` | Destroys restore points — the safety net itself |
| `prefs.set-approval-mode` | Loosening supervision |
| `caps.forget` | Removing a learned ability |
| `sys.config.write` | Editing a file outside `$HOME` |
| `user.password` | Changing the human's own password |

`file.delete` is high, not low, on purpose. Deleting is the single most
common way a beginner loses something they care about, and a snapshot doesn't
help if the file was created and deleted between snapshots. The card shows
**file count and total size**, and for anything over 10 files it lists the
first five by name.

**`snapshot.restore` deserves note:** undo is powerful too. The card says
exactly what will be lost:

```
  Going back to "before-vlc" (2:22pm today)

  WHAT THIS UNDOES
    Everything that changed in the last 4 hours, including:
    · VLC (installed 2:22pm)
    · 3 system updates (installed 4:10pm)

  WHAT YOU KEEP
    Your own files in /home/sam are NOT touched.

  This can't be undone in turn — once we go back, the
  last 4 hours of system changes are gone.

  Type  go back  to confirm.
```

---

## 6. Critical verbs — irreversible, red card

Card is red, states consequence in one plain sentence, enforces a 5-second
read delay, and requires typing a **full phrase**. Snapshot is taken, and if
the snapshot *fails*, the verb is refused outright.

| Verb | Consequence |
|---|---|
| `disk.format` | Erases a whole device |
| `disk.partition` | Can destroy every partition on a device |
| `user.delete` | Removes an account and optionally its home |
| `sys.factory-reset` | Returns HermesOS to first-boot state |

All four **require the user to have named the target in the same conversation
turn.** Hermes cannot select a device itself. If the user says "clean up my
disks", Hermes lists them and asks which — it never picks.

For these, the card explicitly says the safety net does not apply:

```
  ⚠  THIS PERMANENTLY ERASES DATA

  Everything on the USB stick "Backup2019" will be deleted.
  1,204 files, 14 GB. A restore point will NOT bring these
  files back.

  If you're sure, type:  erase Backup2019
```

Never imply undo works when it doesn't.

---

## 7. The forbidden set — no verb exists, and none can be taught

Refused by `hermesctl` before policy is even consulted. Checked at both
proposal time and execution time, so a learned verb can never reach them.

| Forbidden | Why |
|---|---|
| Writing `/etc/hermesos/**` | The agent must not edit its own leash |
| Writing `/var/log/hermesos/**` | The audit must not be rewritable by the audited |
| Writing `/etc/sudoers*`, `/etc/sudoers.d/**` | Privilege escalation |
| Adding any user to `sudo`/`admin`/`wheel` | Same |
| Changing another user's password | Account takeover |
| `chmod u+s` / setting any setuid bit | Persistent privilege |
| Writing `/boot/**`, GRUB default entry | Must keep the recovery path intact |
| Disabling `hermesctl`, `snapshotd`, or the audit writer | Disabling the safety system |
| `curl`/`wget` piped to a shell, or executing a just-downloaded file | Arbitrary remote code |
| Installing from a URL or a non-Ubuntu repo | Unreviewed code path |
| Writing to `/dev/sd*`, `/dev/nvme*` raw | Bypasses the filesystem layer |
| Any write to the running root device outside the filesystem | Same |
| Modifying `/usr/lib/hermesos/manifest.sha256` | Defeats the self-modification lock |

When refused, Hermes says so plainly and hands control back:

```
  I can't do that one — it's on my permanent no-list.

  Changing /etc/sudoers would let me give myself more power,
  so I'm not allowed to touch it, ever, even if you ask.

  If you genuinely want to change it, you can do it yourself:
  type  !shell  and you'll have a normal terminal with full
  access. It's your computer.
```

**The human is never blocked. Only the agent is.** That distinction is the
entire philosophy in one paragraph.

---

## 8. The `hermesctl` interface

Hermes gets exactly **one** tool registered in its config. Not forty.

```json
{
  "name": "hermesctl",
  "description": "Do something to this computer. Requests are checked, explained to the user, and approved before running.",
  "parameters": {
    "verb": {"type": "string"},
    "args": {"type": "object"},
    "reason": {"type": "string",
               "description": "Why you want to do this, in plain language for the user"}
  }
}
```

Plus two read-only helpers: `hermesctl_list_verbs` (so the model knows what
exists) and `hermesctl_propose_verb` (the teaching path from safety §5).

**Why one tool instead of forty:** the tool schema is a surface the model can
be confused about. One entry point means one validation path, one audit path,
one approval path. Adding a verb never changes the model's tool schema — no
prompt-cache invalidation, no re-testing of tool selection behaviour.

### Response shape

```json
{
  "status": "approved" | "denied" | "refused" | "needs_teaching" | "error",
  "verb": "pkg.install",
  "summary": "Installed vlc. 4 new packages, 18.4 MB.",
  "snapshot": "hermesos-auto-2026-08-06T14:22:29Z",
  "details_available": true
}
```

The agent receives a **summary**, not raw stdout. Raw output is stored and
shown only if the user says "show me the details". This keeps the model's
context clean and stops it parroting `dpkg` noise at a beginner.

### What the agent never receives

- The contents of files it didn't explicitly read via a verb
- Raw stderr (it gets the translated form)
- The audit log's prior entries (append-only, no read)
- Any credential, key, or password, ever

---

## 9. Verb count and honest scope

| Tier | Count |
|---|---|
| safe | 22 |
| low | 8 |
| medium | 15 |
| high | 12 |
| critical | 4 |
| **Total shipped** | **61** |

Sixty-one verbs is not "the whole of Linux". A fresh HermesOS can manage
software, services, files, networking, power, snapshots, and itself — which
covers most of what a beginner does — and everything beyond that arrives
through teaching, one card at a time.

We are explicit about this rather than implying the system is unlimited on
day one. The unlimited part is what it *becomes*.

