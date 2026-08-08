"""firstboot/wizard.py — the first-boot wizard state machine.

One source of truth for every screen's copy, options, and safe default. The same
SCREENS data feeds both the headless tests and the interactive HTML preview
(firstboot/preview.html), so what you click is what the OS runs.

The wizard is deliberately *dumb*: it collects answers and walks screens. It
contains no model, no disk writes, no network. The OS wires the collected
answers to real setup steps later. This module is pure state + transitions, so
it is fully testable without a display.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── screen definitions ──────────────────────────────────────────────────────
# Copy is lifted verbatim from docs/07-first-boot.md. `default` marks the
# Enter-reachable safe choice (design rule 3: every screen has a safe default).

SCREENS: list[dict] = [
    {
        "id": "boot",
        "kind": "info",
        "title": "Hermes",
        "body": ["", "getting ready…", ""],
        "footer": "Starting up — press Enter when you're ready.",
        "auto": False,
    },
    {
        "id": "hello",
        "kind": "info",
        "body": [
            "Hello. I'm going to be your computer's voice.",
            "",
            "Instead of hunting through menus, you'll just tell me",
            "what you want — in normal words — and I'll do it.",
            "",
            "Before anything changes on this machine, I'll always",
            "ask you first and explain what it means.",
            "",
            "Setting up takes about five minutes.",
        ],
        "footer": "Press Enter to begin   ·   (Prefer a normal Linux terminal? Press T.)",
        "escape": "terminal",
    },
    {
        "id": "language",
        "kind": "choice",
        "title": "What language should I speak?",
        "body": [
            "Keyboard layout:  US QWERTY   [detected]",
            "",
            "Type here to test it:  (start typing letters)",
        ],
        "options": [
            {"id": "en", "label": "English", "default": True},
            {"id": "es", "label": "Español"},
            {"id": "fr", "label": "Français"},
            {"id": "de", "label": "Deutsch"},
            {"id": "ja", "label": "日本語"},
        ],
        "footer": "↑/↓ to choose · Enter to continue · K to pick a keyboard",
    },
    {
        "id": "time",
        "kind": "choice",
        "title": "Where are you?",
        "body": [
            "Detected: London, United Kingdom   (from your network)",
            "",
            "This sets your clock and time zone. Nothing is sent",
            "anywhere — I worked it out from your connection, and",
            "I can be wrong.",
        ],
        "options": [
            {"id": "detected", "label": "London, United Kingdom", "default": True},
            {"id": "other", "label": "Somewhere else…"},
        ],
        "footer": "Enter to accept · ↓ to change",
    },
    {
        "id": "account_name",
        "kind": "text",
        "title": "Let's make your account.",
        "body": ["What should I call you?"],
        "input_label": "Your name (like \"Sam\" or \"Priya\")",
        "footer": "Type your name · Enter to continue",
        "validate": "nonempty",
    },
    {
        "id": "account_password",
        "kind": "password",
        "title": "Nice to meet you.",
        "body": [
            "Now a password. This protects your computer if someone",
            "else picks it up.",
            "",
            "A few normal words strung together — like",
            "\"correct-horse-battery\" — is both easier to remember",
            "and harder to break than \"P@ssw0rd!\".",
        ],
        "input_label": "Password",
        "footer": "Type a password · Enter to continue",
        "validate": "password",
        "extra_choice": {
            "id": "encrypt",
            "title": "Should I lock the disk itself?",
            "body": [
                "With this on, someone who steals the machine can't read",
                "your files even by removing the drive. The trade-off:",
                "you'll type a second password at every startup, and if",
                "you forget it, the data is gone forever. No exceptions.",
            ],
            "options": [
                {"id": "no", "label": "No — simpler  (recommended if this machine stays home)", "default": True},
                {"id": "yes", "label": "Yes — stronger  (needed if it's a laptop you carry)"},
            ],
        },
    },
    {
        "id": "brain",
        "kind": "choice",
        "title": "Now the interesting part: choosing my brain.",
        "body": [
            "I run entirely on this computer. Nothing you say goes to",
            "the internet, to me, or to any company. You pick how big",
            "a brain this machine can handle.",
            "",
            "I looked at your hardware:  16 GB memory · 8 cores",
            "",
            "All brains are open-source and free; once downloaded they",
            "work with no internet at all.",
        ],
        "options": [
            {"id": "balanced", "label": "Balanced   ← my recommendation for this machine", "default": True,
             "detail": "Good at most things, comfortably fast here.  4.7 GB · ~6 min"},
            {"id": "light", "label": "Light",
             "detail": "Quicker replies, simpler answers.  2.0 GB · ~3 min"},
            {"id": "deep", "label": "Deep",
             "detail": "Noticeably smarter, slower here. Expect a few seconds' pause.  14 GB · ~18 min"},
            {"id": "skip", "label": "Skip for now — set this up later"},
        ],
        "footer": "[Enter] choose Balanced   ·   [?] what IS a brain?",
        "help": (
            "A \"brain\" is a language model — a file containing everything I know"
            " about language, which runs on this computer's own processor.\n\n"
            "Bigger brain = better answers, more disk space, slower replies.\n"
            "Smaller brain = faster, lighter, a bit more literal.\n\n"
            "The one I recommended is called Qwen 2.5 (7 billion parameters, 4-bit)."
        ),
    },
    {
        "id": "download",
        "kind": "progress",
        "title": "Downloading my brain…",
        "body": [
            "████████████████████░░░░░░░░░░  58%",
            "2.7 GB of 4.7 GB · about 3 minutes left",
            "",
            "While that runs, the one thing worth knowing:",
            "",
            "I will never change anything on this computer",
            "without showing you a card first.",
        ],
        "footer": "Download runs in the background · Esc to skip",
        "lesson_card": "approval",  # rotates: approval / undo / teaching
    },
    {
        "id": "first_conversation",
        "kind": "info",
        "title": "Ready. Let's try it once together.",
        "body": [
            "Type this, exactly as written, and press Enter:",
            "",
            '    what\'s on this computer?',
            "",
            "Then try:",
            '    "install a web browser"        ← you\'ll see an approval card',
            '    "make my text bigger"          ← small, instant, reversible',
            '    "what have you done today?"    ← read my notebook',
        ],
        "footer": "Say \"help\" any time · \"!shell\" for a traditional terminal",
    },
]

FLOW = [s["id"] for s in SCREENS]
BY_ID = {s["id"]: s for s in SCREENS}


@dataclass
class Wizard:
    """Headless wizard state. Navigation mirrors what the UI exposes."""
    index: int = 0
    selection: int = 0          # selected option on the current choice screen
    typed: str = ""             # buffer for text/password screens
    answers: dict = field(default_factory=dict)
    done: bool = False
    went_terminal: bool = False

    # ── accessors ────────────────────────────────────────────────────────
    @property
    def screen(self) -> dict:
        return SCREENS[self.index]

    @property
    def screen_id(self) -> str:
        return self.screen["id"]

    def options(self) -> list[dict]:
        return self.screen.get("options", [])

    # ── navigation ───────────────────────────────────────────────────────
    def move(self, delta: int) -> None:
        opts = self.options()
        if not opts:
            return
        self.selection = (self.selection + delta) % len(opts)

    def type_char(self, ch: str) -> None:
        if self.screen["kind"] in ("text", "password"):
            self.typed += ch

    def backspace(self) -> None:
        self.typed = self.typed[:-1]

    def _default_index(self) -> int:
        opts = self.options()
        for i, o in enumerate(opts):
            if o.get("default"):
                return i
        return 0

    def confirm(self) -> Optional[str]:
        """Apply the current screen, advance. Returns next screen id or None."""
        scr = self.screen
        kind = scr["kind"]

        if kind == "choice":
            chosen = self.options()[self.selection]
            self.answers[scr["id"]] = chosen["id"]
            # brain 'skip' still records the choice; account extras handled upstream
            if scr["id"] == "account_password" and "extra_choice" in scr:
                # record the disk-encryption default unless changed elsewhere
                if "encrypt" not in self.answers:
                    self.answers["encrypt"] = "no"
        elif kind in ("text", "password"):
            val = self.typed
            ok, msg = self._validate(scr, val)
            if not ok:
                self.answers["_error"] = msg
                return scr["id"]  # stay put, surface error
            self.answers[scr["id"]] = val
            self.typed = ""
            if "extra_choice" in scr and "encrypt" not in self.answers:
                self.answers["encrypt"] = "no"
        # info / progress: just advance

        self.answers.pop("_error", None)
        self.selection = self._default_index_for_next()
        self.index += 1
        if self.index >= len(SCREENS):
            self.done = True
            return None
        return self.screen_id

    def _default_index_for_next(self) -> int:
        nxt = SCREENS[self.index + 1] if self.index + 1 < len(SCREENS) else None
        if nxt and nxt.get("options"):
            for i, o in enumerate(nxt["options"]):
                if o.get("default"):
                    return i
        return 0

    def escape(self) -> str:
        """User asked for a plain terminal (design rule: never trap anyone)."""
        self.went_terminal = True
        return "terminal"

    # ── validation ───────────────────────────────────────────────────────
    def _validate(self, scr: dict, val: str) -> tuple[bool, str]:
        rule = scr.get("validate")
        if rule == "nonempty":
            if not val.strip():
                return False, "Please type something — even just a first name."
        elif rule == "password":
            if len(val) < 8:
                return False, "A bit longer, please — 8 characters or more keeps you safe."
        return True, ""
