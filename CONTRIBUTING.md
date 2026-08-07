# Contributing to HermesOS

## Branch model

HermesOS is split so each part of the system can move independently. Work
happens on a topic branch, merges into `develop`, and `develop` merges to
`main` at each tagged milestone.

```
main                      ← always in a known-good, documented state; tagged releases
 └── develop              ← integration branch; everything lands here first
      ├── docs/*          ← design documents
      ├── broker/*        ← hermesctl: policy engine, verbs, audit
      ├── firstboot/*     ← the setup wizard
      ├── soul/*          ← Hermes personality + skill bundle
      ├── installer/*     ← ISO build + convert-existing-Ubuntu script
      ├── snapshot/*      ← snapshotd, btrfs/timeshift integration
      └── shell/*         ← hermes-shell, greeter, console UX
```

### Long-lived component branches

| Branch prefix | Owns | Touches |
|---|---|---|
| `docs/` | `docs/**`, `README.md` | Design only, no code |
| `broker/` | `broker/**`, `verbs.d/**` | The safety-critical core |
| `firstboot/` | `firstboot/**` | Wizard screens, model picker |
| `soul/` | `soul/**` | `SOUL.md`, skills, prompt behaviour |
| `installer/` | `installer/**` | `install.sh`, ISO recipe |
| `snapshot/` | `snapshot/**` | Restore points |
| `shell/` | `shell/**` | Login surface, greeter |

Branch names: `broker/verb-validation`, `docs/threat-model`, `soul/tone-pass`.

### Why this split

Each area has a different risk profile and a different reviewer bar. A typo
fix in the greeter is not the same kind of change as touching the policy
engine, and the branch name should make that obvious before anyone opens the
diff.

## The safety review bar

Changes under `broker/**` and `verbs.d/**` are **safety-critical** and held to
a higher standard than anything else in the repo:

1. **No new verb without an `explain` block** written for a non-technical
   reader.
2. **No verb whose `execute` is a shell string.** argv arrays only.
3. **No new argument type without validation tests**, including a traversal
   attempt and an injection attempt.
4. **Risk tier must be justified in the PR body.** "Why isn't this one tier
   higher?" must have an answer.
5. **Nothing may widen what the agent can reach** without an explicit note in
   the PR title: `[CAPABILITY]`.
6. **The forbidden set is append-only.** Removing an entry requires a separate
   PR that does nothing else.

## Commit convention

```
area: short imperative subject

Optional body explaining why, not what.
```

Areas: `docs`, `broker`, `firstboot`, `soul`, `installer`, `snapshot`,
`shell`, `ci`, `chore`.

Examples:
```
broker: reject symlinked user_path after realpath
docs: add threat model section on approval fatigue
soul: soften refusal copy for forbidden verbs
```

## Design-first rule

This project writes the document before the code. If you're adding behaviour
that isn't described in `docs/`, the PR should update the relevant document in
the same change. A feature that exists in code but not in the design docs is a
bug in the docs.

## Testing expectations

| Area | Minimum |
|---|---|
| `broker/` | Unit tests for every arg type; injection + traversal cases; policy decision table |
| `snapshot/` | Create → modify → restore round trip on btrfs and ext4 |
| `firstboot/` | Screen-by-screen snapshot tests; every failure path reachable |
| `installer/` | Full run in a clean VM before merge to `develop` |

## What we will not accept

- Telemetry, analytics, or phone-home of any kind
- A cloud provider as a default
- Any change that lets the agent modify `/etc/hermesos/**`
- "Convenience" flags that disable approvals globally and persist across reboot
- Cryptic error text surfaced to the user without a translation entry
