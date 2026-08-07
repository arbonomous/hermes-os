# broker/ — hermesctl

The safety-critical core. Hermes cannot run commands; it can only ask this
to run a **verb**.

| Module | Job |
|---|---|
| `validate.py` | Types every argument. Where traversal and injection die |
| `verbs.py` | Loads verb files; the forbidden-set guard |
| `cards.py` | Renders approval cards — **the model writes none of this** |
| `dryrun.py` | Parses real tool output into the WHAT CHANGES block |
| `executor.py` | The only place a command runs. Snapshot gate lives here |
| `snapshots.py` | btrfs / timeshift / none, behind one interface |
| `errors.py` | Translates cryptic system errors into plain English |
| `audit.py` | Hash-chained log + the plain-English mirror |

## Run

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m pytest        # 156 tests
./.venv/bin/python demo_cards.py    # see every card type
./.venv/bin/python demo_flow.py     # walk a full request lifecycle
```

## The invariants these tests defend

1. **No shell, ever.** `execute` is an argv array. A verb whose command is a
   string is refused at load. `--pkg={names}` is refused too — a placeholder
   must be a whole argv element, or it would be string interpolation.
2. **Traversal dies at validation.** `user_path` resolves symlinks *before*
   comparing prefixes, so a symlink out of `$HOME` fails as a type error.
3. **The model never writes a warning.** Cards come from the verb file plus
   real dry-run output.
4. **A critical card never reassures.** Tested by asserting the absence of
   "don't worry", "restore point first", and friends.
5. **Learned verbs can't escalate.** They can't be low-risk, can't shadow a
   shipped verb, and hit the same forbidden set.
6. **History can't be rewritten.** Editing or deleting any audit line breaks
   the chain.
7. **No restore point, no change.** A verb declaring `snapshot_before` does
   not run if the snapshot fails. Fail closed, not best-effort.
8. **No cryptic errors.** Known failures are translated with a next step;
   unknown ones are shown verbatim rather than given an invented meaning.

## Not built yet

The CLI entry point, the policy engine's trusted-mode timer, and `undo` as a
user-facing verb (the backends support restore; nothing calls it yet).

`snapshots.py` has never run against a real btrfs filesystem — the backends
are written and unit-tested behind doubles, but the round trip needs a VM.
That is roadmap item 7 and it is not done.
