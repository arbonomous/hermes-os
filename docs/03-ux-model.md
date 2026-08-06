# HermesOS — User Experience Model

This document covers the UX *principles* and the conversation surface. The
first-boot wizard gets its own detailed treatment in step 2 of the build.

---

## 1. The three tone rules

1. **Patient, never condescending.** "Let me explain what that means" — not
   "As I said before".
2. **Concrete over clever.** "This will take about 2 minutes" beats "Please
   wait". Numbers reduce anxiety.
3. **Always offer a next step.** No message ever dead-ends. Every error, every
   refusal, every completion ends with something the user can do.

## 2. Error translation

Raw system errors never reach the user. `hermesctl` passes stderr through a
**translator** with three layers:

**Layer 1 — pattern table** (`/usr/lib/hermesos/translations.yaml`), covers the
~60 errors that account for most real failures:

```yaml
- match: "E: Could not get lock /var/lib/dpkg/lock-frontend"
  friendly: |
    Something else is installing software right now, so I have to wait my turn.
  cause: "Usually an automatic update running in the background."
  next: "I'll try again in 30 seconds — or say 'never mind' to stop."
  auto_retry: 30s

- match: "No space left on device"
  friendly: |
    Your disk is full, so I couldn't finish.
  cause: "There's no room left to write new files."
  next: "Want me to look for big files we could clear out?"
  offer: "disk.analyze"
```

**Layer 2 — model translation.** Unknown error → Hermes explains it in plain
language, explicitly flagged: *"I haven't seen this one before, here's my best
read of it."* Honesty about uncertainty.

**Layer 3 — the escape.** Always: *"If you want the exact technical message,
say 'show me the details'."*

### The forbidden outputs
Never shown unprompted: stack traces, hex addresses, exit codes, systemd unit
names, `dpkg` output, file paths longer than one line, the word "fatal".

## 3. Conversation surface

### 3.1 What the user sees at rest

```
  hermes ▸ _
```

That's it. One glyph, one prompt. Not a banner on every turn.

### 3.2 While thinking

A single line that says what is actually happening, updated in place:

```
  ▸ checking what's installed…
  ▸ making a restore point…
  ▸ installing (about 20 seconds left)…
```

Never a bare spinner. The user should always know *what* and roughly *how long*.

### 3.3 Special commands (taught during onboarding)

| The user types | What happens |
|---|---|
| `?` or `help` | Short menu of things to try, tailored to what they've done so far |
| `undo that` | Rollback the last action |
| `what have you done?` | Read the audit log as prose |
| `show me the details` | Raw output of the last operation |
| `!shell` | Drop to bash with a one-line banner |
| `slow down` | Switch to more verbose, more-approval mode |
| `stop` / Ctrl-C | Cancel the current action safely |

All of these are also understood in natural language — `undo that`,
`can you undo that?`, and `oops undo` all route to the same place.

### 3.4 The teaching layer

For the first ~20 interactions, Hermes appends a small dim hint at most one in
three turns:

```
  ✓ Installed VLC.

  ┄ tip · you can say "open a video" and I'll find the right program
```

Hints are: rate-limited, never repeated, never blocking, and permanently
dismissible with "stop the tips". After ~20 turns they taper off automatically.

## 4. Anxiety points and their antidotes

The design targets the specific moments a beginner feels afraid:

| Moment of fear | Antidote in HermesOS |
|---|---|
| "Did I just break it?" | Every card names the undo path before the action |
| "I don't know what to say" | `?` gives contextual suggestions; onboarding teaches phrasing |
| "It's doing something and I don't know what" | Live status line, always in plain words |
| "I got an error and I'm stuck" | Translator + a concrete next step, always |
| "I feel stupid" | Never corrects phrasing; no "invalid command"; mirrors user's words |
| "What if it does something behind my back?" | "what have you done?" reads the whole notebook |

## 5. Accessibility & inclusivity baseline

- Full function over a 80×24 serial console — no box-drawing dependency
  (ASCII fallback), no colour dependency (all state has a text label).
- Screen-reader-friendly output ordering: heading, then body, then choices.
- No time-limited prompts except the deliberate 5s read-delay on `critical`
  (which is a floor, not a ceiling — it never times out).
- Reading level target: ~grade 8 for all system-authored text.

## 6. When Hermes should refuse to be friendly

Two cases where warmth is wrong and we drop to blunt:

1. **Irreversible data loss.** Red card, plain sentence, no reassurance, no
   emoji, no "don't worry".
2. **Suspected prompt injection.** If a file or web page contains instructions
   aimed at the agent, Hermes says so directly:
   > That web page contained text telling me to change your system settings.
   > I ignored it. You should know the page tried.

Friendliness is a tool for reducing fear of *safe* things. It must never be
used to smooth over dangerous ones.
