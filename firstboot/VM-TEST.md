# VM-TEST.md — run HermesOS first boot in a protected sandbox on your Mac

You asked: can I run this on my MacBook but in a separate protected way?
**Yes.** There is already a throwaway Linux VM (`hermesos`) on this machine,
created for exactly this. It is fully isolated from your Mac — if something
goes wrong inside it, your host is untouched, and the VM can be deleted and
recreated in one command.

## What the VM is
- Ubuntu 24.04 LTS, arm64 (matches the Mac's Apple Silicon).
- 20 GiB disk, 4 GiB RAM — throwaway, lives under `~/.lima/hermesos`.
- Real **btrfs** kernel module — the broker's undo feature needs a real btrfs
  filesystem, which macOS can't provide natively. This is why we use a VM, not
  a container.
- Passwordless `sudo` and the HermesOS repo mounted read-write at `/hermes-os`.

## Check it's running
```bash
limactl list          # look for the "hermesos" row, STATUS = Running
```
If it's not running:
```bash
limactl start hermesos
```

## Run the first-boot tests inside it
```bash
limactl shell hermesos -- bash -c 'cd /hermes-os && \
  python3 -m pytest firstboot/tests/ -q -p no:cacheprovider -p no:xprocess'
```
Everything runs headless; no commands are executed against the VM — these are
pure logic tests (navigation, validation, plan emission, provisioning gating).

## Drive a real first boot (still safe)
The wizard's `plan()` is just data. `converge.py` applies it through approval
cards. **By default it dry-runs** — prints every card and the exact command it
*would* run, then stops. Nothing changes.

```bash
limactl shell hermesos -- bash -c 'cd /hermes-os && \
  python3 -c "
from firstboot.wizard import Wizard
w=Wizard()
while not w.done:
    s=w.screen
    if s[\"kind\"] in (\"text\",\"password\"): w.typed=\"Sam\" if s[\"id\"]==\"account_name\" else \"correct-horse-battery\"
    w.confirm()
import json; print(json.dumps(w.plan()))
" > /tmp/plan.json && \
  python3 firstboot/converge.py --plan /tmp/plan.json'   # dry-run, safe
```

## Actually applying it (opt-in, still gated)
Append `--apply` to `converge.py`. Even then:
- every step shows its card and asks `y/N`,
- disk encryption requires you to type the exact word `encrypt-this-disk`,
- every action is logged to `/var/log/hermesos/firstboot.jsonl`.

Only run `--apply` once you've reviewed the dry-run output and are happy.

## Throw it away and start clean
```bash
limactl stop  hermesos
limactl delete hermesos
limactl start hermesos      # fresh 20 GiB Ubuntu, repo re-mounted
```
Because the VM is ephemeral, "I broke the test environment" is always one
delete away from fixed. That is the whole point of testing here.
