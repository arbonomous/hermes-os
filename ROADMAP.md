# HermesOS Roadmap

## v0.1 — Design & proof (current)

**Goal:** the design is complete and the safety core is demonstrable on a VM.

| # | Deliverable | Branch | Status |
|---|---|---|---|
| 1 | Architecture + safety + UX documents | `docs/` | ✅ done |
| 2 | First-boot wizard design | `docs/` | ✅ done |
| 3 | Tool surface + verb catalogue | `docs/` | ✅ done |
| 4 | `SOUL.md` personality | `soul/` | ✅ done |
| 5 | Installer design + preflight | `installer/` | ✅ 21 tests |
| 6 | `hermesctl` core + executor + snapshot gate | `broker/` | ✅ 156 tests |
| 7 | btrfs round trip on real hardware | `snapshot/` + `integration/` | ✅ 22 assertions in a Linux VM |
| 7b | Model verb-routing reality-check (llama3.1 + qwen2.5, 7B) | `agent/` | ✅ 83% both; refusal weak, hallucination + "clean my disk"→format reproduce cross-model |
| 8 | `hermesd` core loop, wired to reject-and-clarify + ambiguity gate | `agent/` | pending — blocked on #7b findings |
| 9 | First-boot wizard implementation | `firstboot/` | pending |
| 10 | Convert-existing-Ubuntu script | `installer/` | pending |
| 11 | Beginner documentation | `docs/` | pending |

**v0.1 is done when:** a fresh Ubuntu Server 24.04 VM can be converted by one
script, boots to the wizard, downloads a model, and a beginner can install
software through conversation with a real approval card and a working undo.

**The #7b finding changed #8's design.** Routing works (100% in-scope on
llama3.1); blind trust does not. hermesd must validate the model's verb
against the catalogue (reject-and-clarify) and treat vague requests as
"ask, don't guess" — especially anything that could be read as destructive.
See `agent/REALITY-CHECK.md`.

## v0.2 — The ISO

- Bootable installer image (btrfs by default)
- GRUB "previous restore point" entry
- Offline model bundling option
- `hermesos-rescue` on the ISO

## v0.3 — Teaching at scale

- Capability proposal UI hardening
- Shareable verb bundles (`hermesos add-abilities photography`)
- Monthly unused-ability review

## v0.4 — Beyond the console

- Optional local web UI on `127.0.0.1`
- Voice in/out, fully local
- Multi-user with per-user capability sets

## Deliberately not planned

- A desktop environment
- A cloud account or sync service
- Telemetry, ever
