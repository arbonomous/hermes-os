# broker/ — hermesctl

The safety-critical core. Hermes cannot run commands; it can only ask this
to run a **verb**.

| Module | Job |
|---|---|
| `validate.py` | Types every argument. Where traversal and injection die |
| `verbs.py` | Loads verb files; the forbidden-set guard |
| `cards.py` | Renders approval cards — **the model writes none of this** |
| `audit.py` | Hash-chained log + the plain-English mirror |

## Run

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m pytest        # 106 tests
./.venv/bin/python demo_cards.py    # see every card type
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

## Not built yet

The executor (`execve` + snapshot gate), the policy engine's trusted-mode
timer, and the CLI entry point. Validation, verbs, cards and audit are done
and tested; those are the layers a mistake is unrecoverable in.
