"""The executor.

The only place in HermesOS where a command actually runs. Everything else
validates, describes, or records.

Order of operations, and none of it is skippable:

    1. verb exists                  → else refuse
    2. args validate                → else refuse, explain in plain words
    3. render argv, guard again     → else refuse
    4. dry run (if defined)         → produces the WHAT CHANGES text
    5. card rendered by US          → shown to the human
    6. human decides                → denial is logged too
    7. snapshot (if declared)       → FAILURE HERE IS FATAL
    8. execve, no shell             → output captured, timeout enforced
    9. audit the result             → success or failure

Step 7 is the one people are tempted to make best-effort. It isn't. If a
verb declares snapshot_before and no restore point can be made, the verb
does not run.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Callable

from .audit import AuditLog
from .cards import fill, render_approval, render_critical, render_refusal
from .dryrun import summarise
from .errors import friendly_failure
from .snapshots import Snapshot, SnapshotBackend, SnapshotError
from .validate import ValidationError, validate_arg
from .verbs import Verb, VerbError, render_command

# Environment handed to child processes. Deliberately minimal: no inherited
# LD_PRELOAD, no PATH surprises, no locale-dependent output parsing.
SAFE_ENV = {
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
    "DEBIAN_FRONTEND": "noninteractive",
    "HOME": "/nonexistent",
}

DEFAULT_TIMEOUT = 600


class Denied(Exception):
    """The human said no. Not an error — a valid outcome."""


@dataclass
class Result:
    ok: bool
    verb: str
    argv: list[str] = field(default_factory=list)
    exit_code: int | None = None
    output: str = ""
    message: str = ""
    snapshot: Snapshot | None = None


# A prompt function returns True/False for y-n cards, or the typed string
# for confirm-word cards. Injected so tests never need a tty.
Prompt = Callable[[str, Verb], bool | str]


class Executor:
    def __init__(
        self,
        verbs: dict[str, Verb],
        *,
        audit: AuditLog,
        snapshots: SnapshotBackend,
        home: str,
        prompt: Prompt,
        dry_run_only: bool = False,
        runner=subprocess.run,
    ):
        self.verbs = verbs
        self.audit = audit
        self.snapshots = snapshots
        self.home = home
        self.prompt = prompt
        self.dry_run_only = dry_run_only
        self._run = runner if runner is not None else subprocess.run

    # ── the single entry point ──────────────────────────────────────────

    def invoke(self, verb_name: str, args: dict | None = None) -> Result:
        args = args or {}

        verb = self.verbs.get(verb_name)
        if verb is None:
            msg = (
                f"I don't know how to do '{verb_name}' yet. Ask me in your "
                "own words and I'll tell you whether I can learn it."
            )
            self.audit.append(verb=verb_name, decision="unknown", summary=msg)
            return Result(ok=False, verb=verb_name, message=msg)

        # 2 — validate every argument
        try:
            values = self._validate(verb, args)
        except ValidationError as exc:
            self.audit.append(verb=verb_name, decision="refused", reason=str(exc),
                              summary=f"Rejected the arguments for {verb_name}")
            return Result(ok=False, verb=verb_name, message=render_refusal(str(exc)))

        # 3 — render and re-guard
        try:
            argv = render_command(verb, verb.execute, values)
        except VerbError as exc:
            self.audit.append(verb=verb_name, decision="refused", reason=str(exc),
                              summary=f"Blocked the command for {verb_name}")
            return Result(ok=False, verb=verb_name, message=render_refusal(str(exc)))

        # 4 — dry run, which is what WHAT CHANGES is built from
        changes = self._dry_run(verb, values)

        # 5/6 — the human decides
        if verb.needs_approval:
            card = (
                render_critical(verb, values, changes=changes, argv=argv)
                if verb.risk == "critical"
                else render_approval(verb, values, changes=changes, argv=argv,
                                     snapshot=verb.snapshot_before)
            )
            if not self._approved(card, verb):
                self.audit.append(verb=verb_name, decision="denied",
                                  summary=fill(verb.summary, values))
                return Result(ok=False, verb=verb_name,
                              message="No problem — I haven't changed anything.")

        if self.dry_run_only:
            return Result(ok=True, verb=verb_name, argv=argv,
                          message=f"(Dry run — nothing changed.)\n{changes}")

        # 7 — the snapshot gate. Fail closed.
        snap = None
        if verb.snapshot_before:
            try:
                snap = self.snapshots.create(
                    label=fill(verb.summary, values)
                )
            except SnapshotError as exc:
                self.audit.append(verb=verb_name, decision="aborted",
                                  reason="snapshot failed",
                                  summary="Stopped before changing anything")
                return Result(ok=False, verb=verb_name, message=str(exc))

        # 8 — run it
        res = self._execute(argv)

        # 9 — record what happened
        self.audit.append(
            verb=verb_name,
            decision="approved",
            summary=fill(verb.summary, values),
            argv=argv,
            exit_code=res.exit_code,
            snapshot=snap.name if snap else None,
        )
        res.snapshot = snap
        if not res.ok:
            res.message = self._explain_failure(
                verb, res, snap, summary=fill(verb.summary, values)
            )
        return res

    # ── internals ───────────────────────────────────────────────────────

    def _validate(self, verb: Verb, args: dict) -> dict:
        unknown = set(args) - set(verb.args)
        if unknown:
            raise ValidationError(
                f"I don't recognise the option {sorted(unknown)[0]!r} for this."
            )
        values = {}
        for name, spec in verb.args.items():
            if name not in args:
                if spec.required:
                    raise ValidationError(f"I still need to know: {name}.")
                continue
            values[name] = validate_arg(spec, args[name], home=self.home)
        return values

    def _dry_run(self, verb: Verb, values: dict) -> str:
        if not verb.dry_run:
            return "I can't preview this one in advance."
        try:
            argv = render_command(verb, verb.dry_run, values)
        except VerbError:
            return "I couldn't work out the details in advance."
        res = self._execute(argv, timeout=120)
        return summarise(verb.parse_dry_run, res.output, ok=res.ok)

    def _approved(self, card: str, verb: Verb) -> bool:
        answer = self.prompt(card, verb)
        if verb.needs_typed_confirm:
            return isinstance(answer, str) and answer.strip() == verb.confirm_word
        return answer is True

    def _execute(self, argv: list[str], *, timeout: int = DEFAULT_TIMEOUT) -> Result:
        try:
            proc = self._run(
                argv,
                shell=False,                 # never a shell. the whole point.
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=dict(SAFE_ENV),
                cwd="/",
                start_new_session=True,      # child can't grab our terminal
            )
        except FileNotFoundError:
            return Result(ok=False, verb="", argv=argv, exit_code=127,
                          message=f"The program {argv[0]} isn't installed.")
        except subprocess.TimeoutExpired:
            return Result(ok=False, verb="", argv=argv, exit_code=124,
                          message="That took too long, so I stopped it.")
        except PermissionError:
            return Result(ok=False, verb="", argv=argv, exit_code=126,
                          message=f"I'm not allowed to run {argv[0]}.")
        out = (proc.stdout or "") + (proc.stderr or "")
        return Result(ok=proc.returncode == 0, verb="", argv=argv,
                      exit_code=proc.returncode, output=out)

    def _explain_failure(
        self, verb: Verb, res: Result, snap: Snapshot | None, *, summary: str
    ) -> str:
        """Never show a raw exit code as the headline.

        `_execute` may already have written a specific, friendlier reason
        (missing program, timeout, permission). That always wins over the
        generic wording — it tells the user something the exit code can't.
        """
        if res.message:
            # _execute already wrote a specific reason (missing program,
            # timeout, permission). It beats anything we could infer here.
            parts = [res.message]
            if snap:
                parts.append(
                    'Nothing is broken — I made a restore point first. '
                    'Say "undo that" to go back to how things were.'
                )
            parts.append("Want me to try something else?")
            return "\n\n".join(parts)
        return friendly_failure(summary, res.output, snapshot=snap is not None)

