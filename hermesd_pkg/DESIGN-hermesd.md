# hermesd — the conversation loop

The broker is a safe library. `hermesd` is the thing that talks to a person
and uses it. This file specifies the loop and the two guards the
`eval_verb_routing.py` reality-check proved we need.

## The loop

```
user says something
   │
   ▼
Router.route(text)  ──►  Routed{verb, args} | Refuse | Clarify
   │
   ├─ Refuse   → show a card, stop. (out of scope / I can't)
   ├─ Clarify  → ask one question, stop. (too vague to act safely)
   └─ verb     → extract args → validate → Executor.invoke(verb, args)
                                              │
                                    prompts the user with a card
                                              │
                                    runs, or refuses
```

## Guard 1 — reject-and-clarify (the model names verbs it can't)

`eval_verb_routing.py` showed both test models invent `pkg.update`, a verb
that does not exist. `hermesd` **never** calls `Executor.invoke()` with a verb
name the model produced. The router validates the model's output against the
real catalogue first. Unknown verb → refuse-and-ask, never guess.

## Guard 2 — ambiguity gate (vague text never reaches a destructive verb)

Both models routed "clean my disk" → `disk.format`. A beginner phrasing a
*safe* intent got a *destructive* verb. So: if the chosen verb is `critical`
risk and the user's words don't contain a concrete target or an explicit
destructive verb, `hermesd` asks a clarifying question instead of proceeding.
"Exactly which disk? The USB stick or the main drive?" — never a guess.

## What hermesd is NOT (v0.1)

- Not a model. It calls an injected completion function; tests swap in a stub.
- Not a UI. It returns text; the TUI/shell layer (later branches) renders it.
- Not a shell. It can only ever call broker verbs. Same restriction as the
  broker itself.
