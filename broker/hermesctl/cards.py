"""Approval cards.

The card is rendered HERE, from the verb definition and real dry-run output.
The model never writes a single word the user reads in a card. That is the
property that survives a hallucinating or prompt-injected model.
"""
from __future__ import annotations

import textwrap

from .verbs import Verb, quote_for_display

WIDTH = 60
INNER = WIDTH - 4


def _wrap(text: str, indent: str = "  ") -> list[str]:
    """Reflow to the card width.

    Single newlines inside a paragraph are treated as soft wraps and
    reflowed — YAML block scalars break lines at authoring width, which is
    not the card width. A blank line still starts a new paragraph, and a
    line starting with a bullet keeps its own line.
    """
    lines: list[str] = []
    width = INNER - len(indent)
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        raw = [ln.strip() for ln in block.split("\n") if ln.strip()]
        # Bullet/marker lines stay as authored; prose gets joined and reflowed.
        if any(ln[:1] in "+-·*" for ln in raw):
            chunks = raw
        else:
            chunks = [" ".join(raw)]
        for chunk in chunks:
            lines.extend(
                textwrap.wrap(
                    chunk, width=width,
                    initial_indent=indent, subsequent_indent=indent,
                ) or [indent]
            )
    return lines


def _box(lines: list[str], *, marker: str = "") -> str:
    top = "  ┌" + "─" * (WIDTH - 2) + "┐"
    bot = "  └" + "─" * (WIDTH - 2) + "┘"
    out = [top]
    if marker:
        out.append("  │ " + marker.ljust(WIDTH - 3) + "│")
        out.append("  │" + " " * (WIDTH - 2) + "│")
    for ln in lines:
        out.append("  │ " + ln[: WIDTH - 3].ljust(WIDTH - 3) + "│")
    out.append(bot)
    return "\n".join(out)


def render_approval(
    verb: Verb,
    values: dict,
    *,
    changes: str,
    argv: list[str],
    snapshot: bool,
    show_command: bool = False,
) -> str:
    """The standard card for medium/high risk.

    `changes` is parsed from the real dry run — never from the model.
    """
    body: list[str] = []

    headline = fill(verb.summary, values)
    body.append(headline)
    body.append("")

    body.append("WHAT THIS DOES")
    body.extend(_wrap(fill(verb.explain, values)))
    body.append("")

    body.append("WHAT CHANGES")
    body.extend(_wrap(changes or "I couldn't work out the details in advance."))
    body.append("")

    body.append("IF YOU CHANGE YOUR MIND")
    if snapshot:
        body.extend(_wrap(
            'Say "undo that" any time — I\'m making a restore point first.'
        ))
    else:
        body.extend(_wrap("This one doesn't change the system, so there's nothing to undo."))
    body.append("")

    if show_command:
        body.append("THE EXACT COMMAND")
        body.extend(_wrap(quote_for_display(argv)))
        body.append("")

    if verb.needs_typed_confirm:
        body.append(f"To go ahead, type:  {verb.confirm_word}")
        body.append("Or press Esc to cancel.")
    else:
        body.append("[Y] Yes, go ahead    [N] No thanks    [?] Tell me more")

    return _box(body)


def render_critical(verb: Verb, values: dict, *, changes: str, argv: list[str]) -> str:
    """Red card. No reassurance — the absence of warmth is the warning."""
    if verb.consequence is None or verb.confirm_word is None:
        # load_verb() enforces both. Reaching here means a verb was built
        # bypassing the loader, so refuse rather than render a card with a
        # missing warning.
        raise ValueError(
            f"{verb.name}: critical verb has no consequence/confirm_word; "
            "refusing to render a card that understates the risk."
        )
    body: list[str] = []
    body.extend(_wrap(fill(verb.consequence, values), indent=""))
    body.append("")
    body.extend(_wrap(changes, indent=""))
    body.append("")
    body.extend(_wrap(
        "A restore point will NOT bring this back.", indent=""
    ))
    body.append("")
    body.append(f"If you're sure, type:  {verb.confirm_word}")
    body.append("Or press Esc to cancel.")
    return _box(body, marker="⚠  THIS PERMANENTLY ERASES DATA")


def render_teaching(
    *, request: str, verb_name: str, argv: list[str], explanation: str, risk: str
) -> str:
    """Proposal card. The literal command is always expanded here."""
    body: list[str] = []
    body.append("YOU ASKED")
    body.extend(_wrap(f'"{request}"'))
    body.append("")
    body.append("WHAT I'D NEED TO LEARN")
    body.extend(_wrap(f'A new ability called "{verb_name}" that would run:'))
    body.append("")
    body.extend(_wrap(quote_for_display(argv), indent="    "))
    body.append("")
    body.append("WHAT THAT MEANS")
    body.extend(_wrap(explanation))
    body.extend(_wrap(
        f"I'd class this as {risk.upper()} risk, so I'll still ask you "
        "each time before I use it."
    ))
    body.append("")
    body.append("IF YOU SAY YES")
    body.extend(_wrap(
        'I\'ll remember this permanently. Say "what can you do?" to see '
        'everything, or "forget how to do that" to take it back.'
    ))
    body.append("")
    body.append("[Y] Teach me   [N] No   [?] Explain the command")
    return _box(body, marker="I don't know how to do this yet.")


def render_refusal(reason: str) -> str:
    """A forbidden action. Explain, then hand over the keys."""
    return (
        "\n  I can't do that one — it's on my permanent no-list.\n\n"
        + "\n".join(_wrap(reason))
        + "\n\n"
        + "\n".join(_wrap(
            "If you genuinely want to do it, type !shell for a normal "
            "terminal with full access. It's your computer."
        ))
        + "\n"
    )


def humanise(value) -> str:
    """One value as a person would say it: [a, b] -> "a and b"."""
    if isinstance(value, list):
        if len(value) == 1:
            return str(value[0])
        if len(value) == 2:
            return f"{value[0]} and {value[1]}"
        return ", ".join(str(v) for v in value[:-1]) + f", and {value[-1]}"
    return str(value)


def fill(template: str, values: dict) -> str:
    """Render a verb template with human-readable values."""
    return template.format(**{k: humanise(v) for k, v in values.items()})
