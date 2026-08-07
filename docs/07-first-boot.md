# HermesOS — The First Boot Experience

The first five minutes decide whether a beginner stays. This document
specifies the wizard screen by screen: exact copy, timing, failure paths.

**Design rules for the whole wizard:**

1. **One question per screen.** Never a form. Never two decisions at once.
2. **Every screen says why.** A beginner shouldn't have to guess what a choice
   affects.
3. **Every screen has a safe default** reachable by pressing Enter.
4. **Nothing is permanent.** Every choice is changeable later, and each screen
   says so.
5. **No progress bar lies.** Real percentages from real work, or no bar.
6. **Total time to a working conversation: under 10 minutes** on a 100 Mbit
   connection, excluding the model download (which happens in the background
   while onboarding continues).

---

## Screen 0 — Boot (0-40s)

No wall of systemd text. Quiet boot, then a single centred line on a dark
background while services start:

```



                        Hermes


                   getting ready…



```

If boot takes longer than 15s, the line gains a reason:
`getting ready… (checking your hardware)`. Never a bare wait.

**Failure path:** if any critical service fails, we do *not* show a stack
trace. We show:

```
        Something didn't start correctly.

        I can still help you fix it — press Enter to
        open a basic repair conversation, or press S
        for a standard terminal.
```

---

## Screen 1 — Hello (the first thing a human reads)

```
  ┌────────────────────────────────────────────────────────────┐
  │                                                            │
  │                          Hermes                            │
  │                                                            │
  │        Hello. I'm going to be your computer's voice.       │
  │                                                            │
  │        Instead of hunting through menus, you'll just       │
  │        tell me what you want — in normal words — and       │
  │        I'll do it.                                         │
  │                                                            │
  │        Before anything changes on this machine, I'll       │
  │        always ask you first and explain what it means.     │
  │                                                            │
  │        Setting up takes about five minutes.                │
  │                                                            │
  │                                                            │
  │                   Press Enter to begin                     │
  │                                                            │
  │                                                            │
  │        (Prefer a normal Linux terminal? Press T.)          │
  │                                                            │
  └────────────────────────────────────────────────────────────┘
```

**Why this copy:**
- *"your computer's voice"* — a metaphor a non-technical person already owns.
- The safety promise appears on screen **one**, before any choice. Trust is
  established before it's needed, not after something scary happens.
- *"about five minutes"* — a number. Unknown duration is the main source of
  setup anxiety.
- The T escape is present from the very first screen. We are not trapping
  anyone. Paradoxically this makes people *more* willing to continue.

---

## Screen 2 — Language & keyboard

```
  What language should I speak?

    ▸ English
      Español
      Français
      Deutsch
      日本語
      … 12 more  (type to search)

  ────────────────────────────────────────────

  Keyboard layout:  US QWERTY   [detected]

  Type here to test it:  ▸ _

  If those letters look wrong, press K to pick a different layout.


  Enter to continue
```

Keyboard **verification by typing** rather than a dropdown of layout codes. A
beginner cannot tell "pc105/intl/altgr-int" apart, but they can absolutely tell
that pressing a key produced the wrong letter. This one screen prevents the
single most common early-Linux disaster: setting a password on a wrong layout
and being locked out.

---

## Screen 3 — Time & place

```
  Where are you?

    ▸ Detected: London, United Kingdom   (from your network)

      Somewhere else…

  This sets your clock and time zone. Nothing is sent anywhere —
  I worked it out from your connection, and I can be wrong.


  Enter to accept  ·  ↓ to change
```

Note *"nothing is sent anywhere"*. Privacy reassurance appears at the exact
moment the user might wonder about it, not buried in a policy document.

---

## Screen 4 — Your account

```
  Let's make your account.

  What should I call you?

    ▸ _

  This is just your name — like "Sam" or "Priya".
```

Then, on the next screen only:

```
  Nice to meet you, Sam.

  Now a password. This protects your computer if someone
  else picks it up.

    Password:         ▸ ••••••••
    Type it again:    ▸ ••••••••

  ┄ A few normal words strung together — like
    "correct-horse-battery" — is both easier to remember
    and harder to break than "P@ssw0rd!".

  ┄ Nobody can recover this for you. If you're worried
    about forgetting it, write it on paper and keep it
    somewhere safe. That's genuinely fine.
```

**Two deliberate choices:**
- Name and password on **separate screens**. Combined forms make beginners
  rush.
- The "write it on paper" advice is real security guidance for a home machine,
  and it removes a genuine fear. We say *"that's genuinely fine"* because
  beginners have been shamed for this before.

**Optional disk encryption** appears here only if the installer detects it
wasn't set up at partition time:

```
  Should I lock the disk itself?

    ▸ No — simpler  (recommended if this machine stays home)
      Yes — stronger  (needed if it's a laptop you carry)

  With this on, someone who steals the machine can't read
  your files even by removing the drive. The trade-off:
  you'll type a second password at every startup, and if
  you forget it, the data is gone forever. No exceptions.
```

Honest trade-off, real consequence, sane default. Not a checkbox labelled
"LUKS".

---

## Screen 5 — Choosing the brain

The signature screen of HermesOS. This is where we introduce the concept of a
local model to someone who has never heard of one.

```
  ┌────────────────────────────────────────────────────────────┐
  │  Now the interesting part: choosing my brain.              │
  │                                                            │
  │  I run entirely on this computer. Nothing you say goes     │
  │  to the internet, to me, or to any company. That means     │
  │  you pick how big a brain this machine can handle.         │
  │                                                            │
  │  I looked at your hardware:                                │
  │    16 GB memory · 8 cores · no separate graphics card      │
  │                                                            │
  │  ──────────────────────────────────────────────────────    │
  │                                                            │
  │  ▸ Balanced          ← my recommendation for this machine  │
  │      Good at most things, comfortably fast here.           │
  │      4.7 GB download · about 6 minutes                     │
  │                                                            │
  │    Light                                                   │
  │      Quicker replies, simpler answers. Great on            │
  │      older machines.                                       │
  │      2.0 GB download · about 3 minutes                     │
  │                                                            │
  │    Deep                                                    │
  │      Noticeably smarter, noticeably slower on your         │
  │      hardware. Expect a few seconds' pause per reply.      │
  │      14 GB download · about 18 minutes                     │
  │                                                            │
  │    Skip for now — set this up later                        │
  │                                                            │
  │  ──────────────────────────────────────────────────────    │
  │                                                            │
  │  You can change this any time by saying                    │
  │  "use a different brain". Nothing is locked in.            │
  │                                                            │
  │  [Enter] choose Balanced   [?] what IS a brain?            │
  └────────────────────────────────────────────────────────────┘
```

**Why it's built this way:**

- **Names, not model IDs.** "Balanced" not `qwen2.5:7b-instruct-q4_K_M`. The
  real name is one `?` away and shown in the confirmation, so nobody is
  deceived — but nobody is confronted with it either.
- **Download size AND time.** Size alone is meaningless to a beginner; time is
  the thing they actually care about.
- **Hardware read-back.** Showing what we detected makes the recommendation
  feel reasoned rather than arbitrary, and lets a knowledgeable user spot a
  mis-detection.
- **Honest about the trade.** "Deep" openly says *noticeably slower*. We never
  upsell a choice that will make the machine feel broken.
- **Skip is a first-class option.** Someone on hotel wifi must be able to
  finish setup.

Pressing `?`:

```
  A "brain" is a language model — a file containing everything
  I know about language, which runs on this computer's own
  processor.

  Bigger brain = better answers, more disk space, slower replies.
  Smaller brain = faster, lighter, a bit more literal.

  All of them are open-source and free. Once downloaded, they
  work with no internet at all.

  The one I recommended is called Qwen 2.5 (7 billion
  parameters, 4-bit). If those words mean something to you,
  press A for the full technical list.

  Press Esc to go back.
```

The escalation ladder — friendly name → plain explanation → real model ID →
full advanced list — serves all four audiences from one screen without
patronising any of them.

---

## Screen 6 — The download (and the lesson hidden inside it)

The download is dead time. We spend it teaching — this is the highest-value
screen in the wizard and it costs the user nothing.

```
  ┌────────────────────────────────────────────────────────────┐
  │  Downloading my brain…                                     │
  │                                                            │
  │  ████████████████████░░░░░░░░░░░░  58%                     │
  │  2.7 GB of 4.7 GB · about 3 minutes left                   │
  │                                                            │
  │  ──────────────────────────────────────────────────────    │
  │                                                            │
  │  While that runs, here's the one thing worth knowing:      │
  │                                                            │
  │  I will never change anything on this computer             │
  │  without showing you a card like this first.               │
  │                                                            │
  │    ┌──────────────────────────────────────────┐            │
  │    │  I'd like to install VLC                 │            │
  │    │                                          │            │
  │    │  WHAT THIS DOES                          │            │
  │    │    Adds a video player to your computer. │            │
  │    │                                          │            │
  │    │  WHAT CHANGES                            │            │
  │    │    + 4 new programs (18 MB)              │            │
  │    │    · Nothing removed or overwritten      │            │
  │    │                                          │            │
  │    │  IF YOU CHANGE YOUR MIND                 │            │
  │    │    Say "undo that" — I'm making a        │            │
  │    │    restore point first.                  │            │
  │    │                                          │            │
  │    │  [Y] Yes    [N] No    [?] Tell me more   │            │
  │    └──────────────────────────────────────────┘            │
  │                                                            │
  │  Four parts, always in that order:                         │
  │  what it does · what changes · how to undo it · your call. │
  │                                                            │
  │  Saying no is always fine. It costs nothing and I          │
  │  won't be offended.                                        │
  │                                                            │
  └────────────────────────────────────────────────────────────┘
```

The user learns the safety UI **before** they ever face a real one, at a moment
when there is zero pressure and nothing at stake. When the first genuine
approval card appears an hour later, it is already familiar.

Two more cards rotate during longer downloads:

**Card B — undo:**
```
  If anything ever goes wrong, say:

      undo that

  I keep a restore point before every change. Going back
  takes a few seconds and doesn't need any technical
  knowledge.

  This is the safety net under everything else. It's why
  you can afford to experiment.
```

**Card C — teaching:**
```
  Sometimes you'll ask for something I don't know how to
  do yet.

  I won't guess, and I won't fail quietly. I'll show you
  exactly what I'd need to learn, and ask.

  Say yes, and I know it forever. Say "what can you do?"
  any time to see everything you've taught me — and
  "forget how to do that" to take it back.

  This is how HermesOS becomes YOUR computer instead of
  a copy of everyone else's.
```

**Failure path — download interrupted:**
```
  The download stopped — looks like the connection dropped.

  I've kept the 2.7 GB already downloaded, so we won't
  start over.

    ▸ Try again
      Pick a smaller brain instead
      Skip for now, finish setup without me thinking yet

  Nothing is broken. This happens.
```

*"Nothing is broken. This happens."* — five words that prevent a beginner from
concluding they've ruined the installation.

---

## Screen 7 — Your first conversation

Not a "setup complete" screen. A **guided first exchange**, so the user's very
first act is success rather than a blank prompt.

```
  ┌────────────────────────────────────────────────────────────┐
  │  Ready. Let's try it once together.                        │
  │                                                            │
  │  Type this, exactly as written, and press Enter:           │
  │                                                            │
  │      what's on this computer?                              │
  │                                                            │
  │  ▸ _                                                       │
  └────────────────────────────────────────────────────────────┘
```

They type it. Hermes answers for real:

```
  Here's what I can see:

    Disk        238 GB, 12% used — lots of room
    Memory      16 GB
    Network     connected over wifi ("Home-5G")
    Software    412 programs, all up to date
    Restore     1 point, made a few minutes ago

  Nothing looks wrong. Ask me anything else.

  ┄ tip · that was a "read-only" question, so I didn't
    need to ask permission. I only ask when something
    would actually change.
```

That tip teaches the **shape of the safety model** through lived experience
rather than explanation: reading is free, changing asks. One sentence, at the
exact moment it makes sense.

Then, three suggestions — always phrased as sentences the user can copy:

```
  Some things to try:

    "install a web browser"        ← you'll see an approval card
    "make my text bigger"          ← small, instant, reversible
    "what have you done today?"    ← read my notebook

  Or just tell me what you want. Plain words are fine.

  Say "help" any time. Say "!shell" if you want a
  traditional Linux terminal — it's always there.
```

The middle suggestion is deliberately *tiny and instantly visible*. First
successes should be felt, not just reported.

---

## Screen 8 — There isn't one

Setup ends by dissolving into normal use. No "Finish" button, no reboot, no
"Congratulations!" modal. The wizard's last screen **is** the conversation.

The single most common beginner-OS failure is being dumped at a desktop with
no idea what to do next. HermesOS never presents that void: the wizard hands
over mid-sentence to a system that has already asked a question.

---

## Timing budget

| Stage | Target | Hard ceiling |
|---|---|---|
| Boot to Screen 1 | 25 s | 60 s |
| Screens 1-4 (language, place, account) | 90 s | — |
| Screen 5 (brain choice) | 45 s | — |
| Screen 6 (download, teaching) | 6 min | user-cancellable |
| Screen 7 (first exchange) | 60 s | — |
| **Total to productive use** | **~10 min** | |

If the download exceeds 10 minutes, we offer the smaller model *proactively*
rather than making the user wait and resent it.

---

## What we deliberately did NOT put in the wizard

| Omitted | Why |
|---|---|
| Telemetry opt-in | There is no telemetry. Nothing to ask. |
| Account / cloud sign-in | Local-first means no account, ever. |
| Theme / colour picker | Decoration before function. Ask later, in conversation. |
| Feature tour carousel | Nobody reads them. We taught during dead time instead. |
| Licence agreement wall | Shown as a single line with a link, not a scroll-to-accept. |
| "Advanced setup" branch | One path. Advanced users press T on screen 1 and use Ubuntu normally. |
| Gateway / Telegram setup | Off by default. Offer it the first time it'd be useful. |
| Software bundle selection | A beginner cannot evaluate 40 checkboxes. Ask conversationally, later. |

Every omission is a decision to **defer to conversation** rather than
front-load a form. That is the whole thesis of the OS, applied to its own
setup.


