# firstboot/

The first-boot wizard — the five-minutes-that-decide-everything experience.

Spec: `docs/07-first-boot.md` (screen-by-screen copy).

| File | Job |
|---|---|
| `wizard.py` | The state machine. One `SCREENS` list is the single source of truth for every screen's copy, options, and safe default. No model, no disk, no network — pure state, so it's fully testable headless. |
| `preview.html` | The *same* `SCREENS` data, rendered in the browser, fully keyboard-navigable. Open it, click through, confirm the pixels. |
| `tests/` | 12 tests: one-question-per-screen, safe default reachable by Enter, T-escape always available, validation. |

## See it live

    python3 -m http.server 8123     # from this dir
    # open http://localhost:8123/preview.html

Keys: `↑ ↓` choose · `Enter` confirm · `?` help · `T` plain terminal · `Esc` back/skip.

## Run the tests

    python3 -m pytest tests/ -p no:xprocess

(The `-p no:xprocess` flag just disables an unrelated plugin the broker pulls in.)

## What's deliberately NOT here yet

The wizard collects answers. Wiring those answers to real setup steps — creating
the account, writing the locale, starting the model download, handing off to
`hermesd` — belongs to the installer/OS layer and is not in this directory. This
module only decides *what the user chose*.
