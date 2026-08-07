"""Hash-chained audit log.

Every decision is appended, approved or not. Each record carries the hash of
the previous one, so removing or editing any earlier line breaks verification.

Tamper-EVIDENT, not tamper-proof — no TPM, no signing key in v0.1. That is
the honest claim and the docs say so.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "sha256:" + "0" * 64


def _canon(record: dict) -> bytes:
    """Deterministic bytes for hashing: sorted keys, no whitespace drift."""
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def _hash(record: dict) -> str:
    return "sha256:" + hashlib.sha256(_canon(record)).hexdigest()


class AuditLog:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ── writing ─────────────────────────────────────────────────────────

    def _tail(self) -> tuple[int, str]:
        """(last seq, last hash). Genesis values on an empty log."""
        if not self.path.exists():
            return 0, GENESIS
        last = None
        with self.path.open("rb") as fh:
            for line in fh:
                if line.strip():
                    last = line
        if last is None:
            return 0, GENESIS
        rec = json.loads(last)
        return rec["seq"], rec["hash"]

    def append(self, **fields) -> dict:
        seq, prev = self._tail()
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "seq": seq + 1,
            "prev_hash": prev,
            **fields,
        }
        record["hash"] = _hash(record)
        # Append-only, line-buffered, flushed. O_APPEND makes concurrent
        # writes atomic for records under PIPE_BUF.
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return record

    # ── reading ─────────────────────────────────────────────────────────

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def verify(self) -> tuple[bool, str]:
        """Walk the chain. Returns (ok, plain-English explanation)."""
        prev = GENESIS
        expect_seq = 1
        for rec in self.records():
            stored = rec.get("hash")
            body = {k: v for k, v in rec.items() if k != "hash"}
            if _hash(body) != stored:
                return False, (
                    f"Entry {rec.get('seq')} has been altered since it was "
                    "written."
                )
            if rec.get("prev_hash") != prev:
                return False, (
                    f"Entry {rec.get('seq')} doesn't follow on from the one "
                    "before it — something was removed or reordered."
                )
            if rec.get("seq") != expect_seq:
                return False, f"Entry numbering jumps at {rec.get('seq')}."
            prev = stored
            expect_seq += 1
        return True, f"All {expect_seq - 1} entries check out."

    # ── the human-readable mirror ───────────────────────────────────────

    def as_prose(self, limit: int = 20) -> str:
        """"What have you done today?" — the notebook, in English."""
        recs = self.records()[-limit:]
        if not recs:
            return "  I haven't done anything yet."
        out = []
        for r in recs:
            when = _friendly_time(r["ts"])
            verb = r.get("verb", "something")
            decision = r.get("decision")
            if decision == "approved":
                line = f"{when} — You approved: {r.get('summary', verb)}."
                if r.get("snapshot"):
                    line += "\n    I made a restore point first."
                if r.get("exit_code") == 0:
                    line += " It worked."
                elif r.get("exit_code") is not None:
                    line += " It didn't work — I told you what went wrong."
            elif decision == "denied":
                line = f"{when} — You said no to: {r.get('summary', verb)}.\n    Nothing changed."
            elif decision == "refused":
                line = (
                    f"{when} — I couldn't help with: {r.get('summary', verb)}.\n"
                    f"    {r.get('reason', 'It is on my no-list.')}"
                )
            elif decision == "clarify":
                line = (
                    f"{when} — You asked me to clarify: {verb}.\n"
                    f"    I didn't act, because I wasn't sure what you meant."
                )
            elif decision == "taught":
                line = f"{when} — You taught me a new ability: {verb}."
            elif decision == "forgotten":
                line = f"{when} — You removed the ability: {verb}."
            else:
                line = f"{when} — {verb}: {decision}."
            out.append("  " + line)
        return "\n\n".join(out)


def _friendly_time(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    return dt.strftime("%a %-d %b, %-I:%M%p").replace("AM", "am").replace("PM", "pm")
