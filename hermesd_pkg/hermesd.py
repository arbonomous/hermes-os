"""hermesd — the conversation loop.

A thin orchestrator. It does not contain a model, a UI, or a shell. It:
  1. routes the user's text (Router — with the two proven guards)
  2. on Routed, hands the decision to the Executor, which shows a card and
     (if approved) runs the verb
  3. on Refuse / Clarify, returns plain text for the UI to show

Every unsafe action still flows through the broker. hermesd cannot do anything
the catalogue doesn't define. Same restriction as the broker itself.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Make the broker package importable. hermesd is built on top of the broker
# (broker/hermesctl) and never bypasses it.
_BROKER = str(Path(__file__).resolve().parents[1] / "broker")
if _BROKER not in sys.path:
    sys.path.insert(0, _BROKER)

from hermesctl.audit import AuditLog  # noqa: E402
from hermesctl.executor import Executor
from hermesctl.snapshots import SnapshotBackend, detect
from hermesctl.verbs import load_all

from .router import Clarify, Refuse, Routed, Router

CompleteFn = Callable[[str], str]


@dataclass
class Turn:
    text: str            # what hermesd says to the user this turn
    card: str = ""       # the approval card that was shown, if any


@dataclass
class _Decision:
    """Holds the approval answer for the current turn.

    The Executor decides by calling back into hermesd with the rendered card.
    We capture that card (so the UI can show exactly what was displayed) and
    return the per-turn approve/typed answer.
    """
    approve: bool = True
    typed: str | None = None
    card: str = ""


class Hermesd:
    def __init__(self, *, verbs_dir: str | None = None, complete: CompleteFn,
                 home: str = "/home/hermes",
                 audit_path: str = "/var/log/hermes/audit.jsonl",
                 dry_run: bool = False, runner=None, snapshots: SnapshotBackend | None = None):
        repo = Path(__file__).resolve().parents[1]
        self.verbs = load_all(Path(verbs_dir) if verbs_dir else repo / "verbs.d")
        self.router = Router(self.verbs, complete)
        self.audit = AuditLog(Path(audit_path))
        self.home = home
        self.dry_run = dry_run
        self._decision = _Decision()
        self._executor = Executor(
            self.verbs, audit=self.audit,
            snapshots=snapshots if snapshots is not None else detect(),
            home=home, prompt=self._prompt, dry_run_only=dry_run, runner=runner,
        )

    def _prompt(self, card: str, verb) -> bool | str:
        # Captures the exact card the broker displayed, then answers the
        # per-turn decision. The broker never decides — hermesd does, from the
        # user's response.
        self._decision.card = card
        if verb.needs_typed_confirm:
            return self._decision.typed if self._decision.typed is not None \
                else verb.confirm_word
        return self._decision.approve

    def run_turn(self, user_text: str, *, approve: bool = True,
                 typed: str | None = None) -> Turn:
        """One conversational turn.

        approve / typed let a caller (or test) make the yes/no decision that a
        real UI would surface via the card. Keeps hermesd testable without a
        TUI and without a live model.
        """
        self._decision = _Decision(approve=approve, typed=typed)
        outcome = self.router.route(user_text)

        if isinstance(outcome, Refuse):
            self.audit.append(decision="refused", verb=outcome.reason,
                               argv=[], summary=user_text,
                               reason="out of scope")
            return Turn(text=outcome.reason + (f" {outcome.ask}" if outcome.ask else ""))

        if isinstance(outcome, Clarify):
            self.audit.append(decision="clarify", verb=outcome.question,
                               argv=[], summary=user_text)
            return Turn(text=outcome.question)

        # Routed — the broker shows the card and runs it (or not, per decision).
        self._decision.card = ""
        res = self._executor.invoke(outcome.verb, outcome.args)
        return Turn(text=res.message, card=self._decision.card)

    def summary(self) -> str:
        """Plain-English mirror of today's decisions (SOUL: nothing hidden)."""
        return self.audit.as_prose()
