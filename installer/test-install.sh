#!/usr/bin/env bash
# Test matrix for installer/install.sh (docs/06-install.md §7).
# Uses the HERMESOS_FAKE_* seams to simulate machines. No root, no changes.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SH="$HERE/install.sh"
PASS=0; FAIL=0

ok()   { printf '  PASS  %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  FAIL  %s — %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }

# good_machine: ubuntu 24.04, 16 GB, 100 GB free, btrfs, root, not installed
env_good() {
  export HERMESOS_FAKE_OS_ID=ubuntu HERMESOS_FAKE_OS_VER=24.04 \
         HERMESOS_FAKE_RAM_GB=16 HERMESOS_FAKE_FREE_GB=100 \
         HERMESOS_FAKE_FSTYPE=btrfs HERMESOS_FAKE_ROOT=1 \
         HERMESOS_ROOT_PREFIX="$TMP/empty"
}

# run <label> <expected_exit> <must_contain> -- runs with current env
run() {
  local label="$1" want_exit="$2" want_text="$3"; shift 3
  local out rc
  out=$("$SH" "$@" </dev/null 2>&1); rc=$?
  if [ "$rc" -ne "$want_exit" ]; then
    bad "$label" "exit $rc, wanted $want_exit"; return
  fi
  if [ -n "$want_text" ] && ! grep -qi -- "$want_text" <<<"$out"; then
    bad "$label" "missing text: $want_text"; return
  fi
  ok "$label"
}

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/empty"

echo ""
echo "[1] refuses machines it cannot support"
env_good; export HERMESOS_FAKE_OS_ID=debian
run "refuses non-Ubuntu" 1 "isn't Ubuntu"

env_good; export HERMESOS_FAKE_OS_VER=22.04
run "refuses Ubuntu 22.04" 1 "not 24.04"

env_good; export HERMESOS_FAKE_RAM_GB=4
run "refuses 4 GB RAM" 1 "enough memory"

env_good; export HERMESOS_FAKE_FREE_GB=5
run "refuses 5 GB free" 1 "enough disk"

env_good; export HERMESOS_FAKE_ROOT=0
run "refuses without root" 1 "administrator permission"

env_good; mkdir -p "$TMP/done/etc/hermesos"; touch "$TMP/done/etc/hermesos/.installed"
export HERMESOS_ROOT_PREFIX="$TMP/done"
run "refuses if already installed" 1 "already"

echo ""
echo "[2] every refusal explains and gives a next step"
env_good; export HERMESOS_FAKE_RAM_GB=4
out=$("$SH" </dev/null 2>&1)
grep -q "What to do:" <<<"$out" && ok "refusal names a next step" \
  || bad "refusal names a next step" "no 'What to do:'"
grep -qE '\b(errno|Traceback|E:|exit code)\b' <<<"$out" \
  && bad "refusal is jargon-free" "leaked technical noise" \
  || ok "refusal is jargon-free"

echo ""
echo "[3] accepts a good machine"
env_good
run "preflight passes" 0 "can run HermesOS" --preflight

echo ""
echo "[4] dry run changes nothing and prints the plan"
env_good
run "dry-run exits clean" 0 "Dry run" --dry-run
env_good
out=$("$SH" --dry-run </dev/null 2>&1)
for block in "I WILL ADD" "I WILL CHANGE" "I WILL NOT" "IF YOU CHANGE YOUR MIND"; do
  grep -q "$block" <<<"$out" && ok "plan has: $block" || bad "plan has: $block" "absent"
done
grep -q "hermesos-uninstall" <<<"$out" && ok "plan names the uninstaller" \
  || bad "plan names the uninstaller" "absent"

echo ""
echo "[5] warns about degraded undo on ext4 only"
env_good; export HERMESOS_FAKE_FSTYPE=ext4
out=$("$SH" --dry-run </dev/null 2>&1)
grep -q "slower" <<<"$out" && ok "ext4 warns undo is slower" \
  || bad "ext4 warns undo is slower" "no warning"
env_good
out=$("$SH" --dry-run </dev/null 2>&1)
grep -q "slower" <<<"$out" && bad "btrfs stays quiet" "warned anyway" \
  || ok "btrfs stays quiet"

echo ""
echo "[6] refusing consent is safe"
env_good
out=$(printf 'no\n' | "$SH" 2>&1); rc=$?
[ "$rc" -eq 0 ] && grep -q "Nothing was changed" <<<"$out" \
  && ok "typing 'no' stops cleanly" || bad "typing 'no' stops cleanly" "rc=$rc"
env_good
out=$(printf 'YES\n' | "$SH" 2>&1)
grep -q "Nothing was changed" <<<"$out" && ok "only exact 'yes' proceeds" \
  || bad "only exact 'yes' proceeds" "accepted 'YES'"

echo ""
echo "[7] shell hygiene"
bash -n "$SH" && ok "parses cleanly" || bad "parses cleanly" "syntax error"
grep -q 'set -euo pipefail' "$SH" && ok "strict mode on" || bad "strict mode on" "absent"

echo ""
echo "=============================================="
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
