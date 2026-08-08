# firstboot/ — the first-boot provisioning layer

The wizard (`wizard.py`) collects answers and emits a plan (`plan()`) of
broker-flavoured intents. Those intents are turned into real actions here,
in the privileged first-boot runner — a separate trust boundary from the
unprivileged assistant broker.

## Files
| File | Job |
|---|---|
| `wizard.py` | State machine. Collects answers. Emits `plan()`. Does nothing. |
| `apply.py` | `Runner` — applies a plan through approval cards. Allowlisted commands only. |
| `converge.py` | CLI: load a plan JSON, dry-run or `--apply` it at real first boot. |
| `firstbootd.py` | Systemd service entry point: gated by `/etc/hermesos/.setup-pending`. |
| `firstbootd.service` | systemd unit (oneshot, root, dry-run default). |
| `preview.html` | Browser preview of the wizard UX (no execution). |
| `tests/` | Headless tests. No display, no commands run. |
| `VM-TEST.md` | How to run/test first boot in the `hermesos` Lima VM. |

## Why provisioning is NOT a broker verb
The unprivileged broker (`broker/hermesctl/verbs.py`) permanently refuses
`useradd`, `passwd`, `chpasswd`, `curl`, `wget`, `mkfs`, … — by design, so the
assistant can never escalate or fetch-and-execute. Creating your account,
setting locale, and downloading the model are *provisioning* done once as
root at first boot. Different boundary → different module. See `apply.py`'s
module docstring.

## Safety properties (proven in tests)
- `runner.dry_run` is the default — it renders every card + exact command and
  runs nothing.
- `disk.encrypt` is gated behind the typed word `encrypt-this-disk`; anything
  else is skipped.
- Every step is logged to `/var/log/hermesos/firstboot.jsonl`.

## Testing it for real — without touching your Mac
There is a prepared Lima VM, `hermesos` (Ubuntu 24.04 arm64, btrfs in kernel,
passwordless sudo, repo mounted at `/hermes-os`). It is throwaway and isolated
from your host — a perfect sandbox for first-boot testing. See `VM-TEST.md`.

## Run a plan through the runner (programmatically, safe)
```python
from firstboot.wizard import Wizard
from firstboot.apply import Runner

w = Wizard()
while not w.done:           # ...drive the screens...
    w.confirm()
plan = w.plan()             # list of intents
results = Runner(plan=plan, prompt=lambda c: True).apply()  # dry-run by default
```
