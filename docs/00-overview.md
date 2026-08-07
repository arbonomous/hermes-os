# HermesOS — Overview & Design Contract

**Version:** 0.1 (MVP design)
**Base:** Ubuntu Server 24.04 LTS (amd64/arm64)
**Heart:** Hermes Agent (upstream, unforked)
**Model runtime:** Ollama, local-only

---

## 1. What HermesOS is

HermesOS is Ubuntu Server 24.04 with a conversation bolted on as the primary
interface. You talk to your computer; it explains what it wants to do; you say
yes or no; it does it and writes down what happened.

It is **not** a new kernel, a new package manager, or a new init system. Every
change we make is additive and reversible. Under the friendly surface it is a
boring, well-understood Ubuntu box — which is exactly why it is safe.

## 2. The design contract

Two principles, and they are ranked. When they conflict, **safety wins** — but
safety must be expressed in friendly language, never as a wall of jargon.

### Principle 1 — Safety First
| Rule | Concrete meaning |
|---|---|
| Hard to break | No agent action can leave the machine unbootable without passing a snapshot gate |
| Approval by default | Every system-modifying action stops and asks, in plain English |
| Full audit | Every action, approved or denied, is appended to a tamper-evident log |
| One-command rollback | `undo` / "undo the last thing you did" restores the previous snapshot |
| Capability-based | Hermes runs as an unprivileged user with a fixed, enumerable list of allowed operations |
| Dry-run everywhere | Dangerous ops show exactly what *would* happen before they happen |
| Plain-language warnings | "This will erase the photos on the USB stick" — not `wipefs -a /dev/sdb` |

### Principle 2 — Extreme User-Friendliness
| Rule | Concrete meaning |
|---|---|
| Beginner-installable | One ISO, or one curl-to-bash on a fresh Ubuntu Server |
| Conversation-first | The default login shell *is* Hermes, not bash |
| Zero cryptic errors | Every failure is translated: what broke, why, what to do next |
| Beautiful first boot | A calm, paced, welcoming wizard — not a dpkg log |
| Gentle teaching | Onboarding teaches *how to ask*, with worked examples |
| Never intimidating | Patient tone, no shaming, no "RTFM", always an escape hatch |

## 3. The thing that makes it yours

HermesOS is not a fixed set of features you learn to operate. It is a system
that **grows abilities as you ask for them.**

When you want something it can't do yet, it doesn't fail — it proposes:
*"I don't know how to do this yet. Here's exactly what I'd need to learn.
Want to teach me?"* You see the literal command, in plain language, before
you agree. Say yes and the ability is permanent, listable, and removable.

Six months in, your HermesOS will have abilities no other HermesOS has,
because they were shaped by what you actually asked for. That is the point of
the whole project: **an operating system that converges on you**, instead of
you converging on it.

Every one of those abilities arrived through a card you read and approved, is
written in your notebook, and can be taken back with *"forget how to do that"*.
Full mechanism in `02-safety-model.md` §5.

## 4. Non-goals for v0.1

Explicitly out of scope, so we don't drown:

- No desktop environment (GNOME/KDE). Console + optional web UI only.
- No custom kernel, no custom packaging, no PPA.
- No cloud models by default. Local-first, offline-capable after setup.
- No multi-user management. Single primary human in v0.1.
- No fork of Hermes Agent. We ship configuration, wrappers, and a personality —
  upstream stays upstream so it keeps updating cleanly.

## 5. The three surfaces a user touches

1. **The greeting** — what appears when the machine boots. Warm, short, offers
   three things to try.
2. **The conversation** — Hermes on tty1, and optionally over SSH / a local web
   page. This is 95% of use.
3. **The approval card** — the moment before anything changes. This is the most
   safety-critical UI in the entire system and gets the most design attention
   (see `03-ux-model.md`).

Everything else — systemd, apt, btrfs, ollama — is machinery the user should
never have to see, but that an advanced user can always drop into with `!shell`.

## 6. Glossary (for the docs, and for the user)

| Term we use with the user | What it really is |
|---|---|
| "Restore point" | A btrfs snapshot (or Timeshift snapshot on ext4) |
| "Safety check" | The approval gate + policy engine decision |
| "Your notebook" | The audit log, readable as plain English |
| "The brain" | The Ollama model currently loaded |
| "Practice mode" | Dry-run: shows the plan, changes nothing |
| "Deep tools" | Raw shell access, hidden behind `!shell` |

We never say: sudo, systemd unit, apt transaction, subvolume, PATH, daemon —
unless the user asks a question that uses those words first. Then we mirror
their vocabulary.

## 7. Document map

| File | Contents |
|---|---|
| `00-overview.md` | This file — vision, contract, non-goals |
| `01-architecture.md` | System layers, components, boot flow |
| `02-safety-model.md` | Approvals, capabilities, audit, rollback (detail) |
| `03-ux-model.md` | Tone, error translation, conversation surface |
| `07-first-boot.md` | The first-boot wizard, screen by screen |
| `04-tools.md` | The exact tool surface + safety wrappers |
| `05-soul.md` | Hermes' system-level personality |
| `06-install.md` | Installer / converter script design |
