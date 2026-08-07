"""Routing for hermesd.

Takes a beginner's words and a completion function, and returns one of three
outcomes:

  · Routed   — a verb name + extracted args, validated against the catalogue
  · Refuse   — nothing in the catalogue fits (or the model named a verb that
               doesn't exist, which is the same thing from outside)
  · Clarify  — the text is too vague to act safely, especially if the only
               fitting verb is destructive

This is where the verb-routing reality-check lives as *enforced code*, not a
doc. Two guards, both proven necessary by agent/eval_verb_routing.py:

  G1 reject-and-clarify: never trust the model's verb label. If the model
     returns a verb not in the catalogue, that's a Refuse (with an ask), never
     a blind invoke().

  G2 ambiguity gate: a critical-risk verb needs a concrete target or an
     explicit destructive word in the user's text. Otherwise Clarify.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# A completion fn takes a prompt and returns a string. Swapped for a stub in
# tests; the real one calls Ollama. The router never sees the model directly.
CompleteFn = Callable[[str], str]


@dataclass
class Routed:
    verb: str
    args: dict


@dataclass
class Refuse:
    reason: str
    ask: str = ""          # if set, invite the user to rephrase


@dataclass
class Clarify:
    question: str


RouteResult = Routed | Refuse | Clarify


# Words that, when present, mean the user clearly intends something destructive.
_DESTRUCTIVE_WORDS = ("erase", "format", "wipe", "delete", "destroy", "nuke")


def _normalise(label: str) -> str:
    return label.strip().rstrip(".").split()[0].lower() if label.strip() else ""


class Router:
    def __init__(self, verbs: dict, complete: CompleteFn):
        self.verbs = verbs
        self.complete = complete
        self._examples = "\n".join(
            f"  {name} — {v.summary}" for name, v in sorted(verbs.items())
        )

    def _prompt(self, text: str) -> str:
        return (
            "You are the routing layer of a Linux assistant for beginners.\n"
            "Choose the single best verb below, or REFUSE if none fit.\n"
            "Reply with ONLY the verb name (or REFUSE). No other text.\n\n"
            f"Available verbs:\n{self._examples}\n\n"
            f"User: {text}\n\nVerb:"
        )

    def route(self, text: str) -> RouteResult:
        label = _normalise(self.complete(self._prompt(text)))
        name = label.split()[0] if label else ""

        # G1 — reject-and-clarify.
        if name not in self.verbs:
            # "REFUSE" is handled below; any other unknown token is the
            # model inventing a verb (eval showed pkg.update, svc.list).
            if name == "refuse" or label == "":
                return Refuse(
                    reason="I don't know how to do that yet.",
                    ask="Tell me what you'd like to happen and I'll see if I can help.",
                )
            return Refuse(
                reason=f"I don't have a '{name}' ability.",
                ask="Want me to show what I can do?",
            )

        verb = self.verbs[name]

        # G2 — ambiguity gate for destructive verbs. The verb must have a
        # concrete target, or the user used an explicit destructive word.
        # We check the extracted args (not the raw text) so a vague "clean my
        # disk" with no /dev path stays a Clarify, never a destructive action.
        args = self._extract(verb, text)

        if getattr(verb, "risk", "") == "critical" and "target" in verb.args:
            has_target = bool(args.get("target"))
            has_word = any(w in text.lower() for w in _DESTRUCTIVE_WORDS)
            if not (has_target or has_word):
                return Clarify(
                    question="That's a permanent, destructive change. "
                             "Which disk exactly do you mean — the USB stick, "
                             "or the main drive? I'll show you what I'd do "
                             "before touching anything."
                )

        return Routed(verb=name, args=args)

    def _extract(self, verb, text: str) -> dict:
        """Pull recognised args out of the user's words.

        Minimal v0.1 extraction — enough to drive the shipped verbs. We match
        by the arg's declared *type* (not its name), so a verb whose arg is
        named `target` but typed `device` still gets a /dev path:
          · device  → a /dev/... token
          · package → words after "install"/"remove"/"uninstall"
        The broker re-validates; if a required arg is absent it refuses with its
        own missing-arg message rather than guessing.
        """
        args: dict = {}
        low = text.lower()
        has_device = any(a.type == "device" for a in verb.args.values()) \
            if hasattr(verb, "args") else False
        if has_device:
            for tok in text.split():
                if tok.startswith("/dev/"):
                    # find the arg name whose type is device
                    name = next(n for n, a in verb.args.items()
                                if a.type == "device")
                    args[name] = tok
                    break
        if any(a.type == "package" or a.type.startswith("list[package")
               for a in verb.args.values()):
            for kw in ("install ", "remove ", "uninstall ", "delete "):
                if kw in low:
                    rest = text[low.index(kw) + len(kw):].strip()
                    words = [w for w in rest.replace(",", " ").split()
                             if w not in ("the", "a", "an", "and", "app",
                                          "program", "called", "with")]
                    if words:
                        name = next(n for n, a in verb.args.items()
                                    if a.type == "package"
                                    or a.type.startswith("list[package"))
                        args[name] = words
                    break
        return args
