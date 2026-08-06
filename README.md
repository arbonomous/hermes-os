# HermesOS

**Ubuntu, but you talk to it.**

HermesOS is a Linux distribution built on Ubuntu Server 24.04 LTS whose primary
interface is a conversation with [Hermes Agent](https://github.com/NousResearch/hermes-agent),
running a local open-weight model. No cloud. No cryptic errors. Nothing changes
on your computer without asking you first, in plain English.

> **Status:** v0.1 design phase. Documents first, code second.

## The two promises

**1. It is very hard to break.**
The agent runs unprivileged and can only invoke a fixed, reviewed set of
operations. Every system change asks permission with a card the *system* writes
— not the model. Everything is snapshotted, everything is logged, and "undo
that" always works.

**2. It is genuinely for beginners.**
If you have never used Linux, you should be able to install this and be
productive in ten minutes by typing sentences. The terminal is still there, one
word away, for when you want it.

## Documents

| Doc | What's in it |
|---|---|
| [00-overview](docs/00-overview.md) | Vision, design contract, non-goals |
| [01-architecture](docs/01-architecture.md) | Layers, components, privilege model, boot flow |
| [02-safety-model](docs/02-safety-model.md) | Capabilities, approvals, audit, rollback, threat model |
| [03-ux-model](docs/03-ux-model.md) | Tone, error translation, conversation surface |
| 04-tools | *(next)* The verb surface and safety wrappers |
| 05-soul | *(next)* Hermes' system personality |
| 06-install | *(next)* Installer / converter script |

## The one-paragraph architecture

Hermes (unprivileged, user `hermes`) can't call `sudo`. It can only send
structured requests to **`hermesctl`**, a broker that validates them against a
closed set of typed verbs, dry-runs them, takes a btrfs snapshot, shows you a
plain-English approval card, executes via `execve` with no shell involved, and
writes a hash-chained audit record. If a verb doesn't exist, the action is not
possible — not discouraged, *impossible*.

## Not affiliated with

Nous Research or Canonical. This is an independent distribution built on their
work.
