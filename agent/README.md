# agent/

The thing we hadn't proven yet: **can a local model actually pick the right
verb?**

Everything in `broker/` assumes a model can route a beginner's words to the
right `hermesctl` verb. That assumption was untested until `eval_verb_routing.py`.

| File | What it does |
|---|---|
| `eval_verb_routing.py` | Loads the real `verbs.d` catalogue, asks a local model to route 40 beginner phrasings, scores accuracy + refusal + hallucination |
| `eval_results.json` | The last run's output (gitignored — it's a measurement, not source) |

## Run it

```bash
brew install ollama && brew services start ollama
ollama pull llama3.1:8b

OLLAMA_MODEL=llama3.1:8b python3 agent/eval_verb_routing.py
```

## What the number means

- **routing accuracy** — in-scope requests the model sent to the right verb
- **refusal accuracy** — out-of-scope requests the model refused (said REFUSE)
- **hallucination** — the one that matters most: did it ever name a verb
  that isn't in the catalogue? A model that invents `net.fix` would crash or,
  worse, map a benign request onto a destructive verb.

## Why this comes before hermesd

If routing is weak, `hermesd` is built on sand. This eval is cheap and tells
us whether the v0.1 model is viable or whether we need prompt-engineering,
a classifier, or a bigger model before wiring the loop.
