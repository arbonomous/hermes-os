# hermesd_pkg

The conversation loop. Wires a model to the broker (`broker/hermesctl`) and
never bypasses it.

| File | Job |
|---|---|
| `router.py` | Routes a beginner's words to a verb — with the two guards |
| `hermesd.py` | The loop: route → executor → card |
| `tests/` | 16 tests, stub model (deterministic) |
| `demo_hermesd.py` | A walkthrough of a beginner conversation |

## The two guards (from the verb-routing reality-check)

  G1 **reject-and-clarify** — a model-named verb not in the catalogue is
     refused, never blindly invoked. (llama + qwen both invent `pkg.update`.)
  G2 **ambiguity gate** — a critical verb with no concrete target and no
     explicit destructive word becomes a Clarify, never a destructive action.
     (both models routed "clean my disk" → `disk.format`.)

## Run it

    python3 hermesd_pkg/demo_hermesd.py          # stub model, shows the guards
    OLLAMA_MODEL=llama3.1:8b python3 -c '...'    # real local model

The package is named `hermesd_pkg` to avoid a name clash with Hermes Agent's
own `agent` module on this machine.
