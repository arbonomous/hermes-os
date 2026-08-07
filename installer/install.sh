#!/usr/bin/env bash
# HermesOS converter — turns Ubuntu Server 24.04 into HermesOS.
#
#   sudo ./install.sh              convert this machine
#   sudo ./install.sh --dry-run    print the plan, change nothing
#   ./install.sh --preflight       check only, no root needed
#
# Design rules (docs/06-install.md):
#   · Refuse early and explain, never half-convert
#   · Print the plan and wait before touching anything
#   · Idempotent — safe to run twice
#   · Every message is a plain sentence with a next step

set -euo pipefail

VERSION="0.1.0"
MIN_RAM_GB=8
MIN_FREE_GB=15
MARKER=/etc/hermesos/.installed

DRY_RUN=0
PREFLIGHT_ONLY=0
ASSUME_YES=0

# Test seams — let the harness simulate any machine.
: "${HERMESOS_FAKE_OS_ID:=}"
: "${HERMESOS_FAKE_OS_VER:=}"
: "${HERMESOS_FAKE_RAM_GB:=}"
: "${HERMESOS_FAKE_FREE_GB:=}"
: "${HERMESOS_FAKE_FSTYPE:=}"
: "${HERMESOS_FAKE_ROOT:=}"
: "${HERMESOS_ROOT_PREFIX:=}"

for a in "$@"; do
  case "$a" in
    --dry-run)   DRY_RUN=1 ;;
    --preflight) PREFLIGHT_ONLY=1 ;;
    --yes)       ASSUME_YES=1 ;;
    --version)   echo "$VERSION"; exit 0 ;;
    -h|--help)   sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "I don't recognise the option '$a'."; echo "Try --help."; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
rule() { printf '  %s\n' "────────────────────────────────────────────────────────"; }

# A refusal is never a bare exit code: what, why, what next.
refuse() {
  local what="$1" why="$2" next="$3"
  say ""
  say "  I can't install here — $what"
  say ""
  say "  $why"
  say ""
  say "  What to do: $next"
  say ""
  exit 1
}

# ── facts about this machine ────────────────────────────────────────────
os_id()   { [ -n "$HERMESOS_FAKE_OS_ID" ] && { echo "$HERMESOS_FAKE_OS_ID"; return; }
            . /etc/os-release 2>/dev/null && echo "${ID:-unknown}" || echo unknown; }
os_ver()  { [ -n "$HERMESOS_FAKE_OS_VER" ] && { echo "$HERMESOS_FAKE_OS_VER"; return; }
            . /etc/os-release 2>/dev/null && echo "${VERSION_ID:-0}" || echo 0; }
ram_gb()  { [ -n "$HERMESOS_FAKE_RAM_GB" ] && { echo "$HERMESOS_FAKE_RAM_GB"; return; }
            awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0; }
free_gb() { [ -n "$HERMESOS_FAKE_FREE_GB" ] && { echo "$HERMESOS_FAKE_FREE_GB"; return; }
            df -BG --output=avail / 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0; }
fstype()  { [ -n "$HERMESOS_FAKE_FSTYPE" ] && { echo "$HERMESOS_FAKE_FSTYPE"; return; }
            findmnt -no FSTYPE / 2>/dev/null || echo unknown; }
is_root() { [ -n "$HERMESOS_FAKE_ROOT" ] && { [ "$HERMESOS_FAKE_ROOT" = 1 ]; return; }
            [ "$(id -u)" -eq 0 ]; }
installed() { [ -f "${HERMESOS_ROOT_PREFIX}${MARKER}" ]; }

# ── preflight ───────────────────────────────────────────────────────────
preflight() {
  local id ver ram free
  id=$(os_id); ver=$(os_ver); ram=$(ram_gb); free=$(free_gb)

  if installed; then
    refuse "HermesOS is already here." \
      "This machine has already been converted, so there's nothing to do." \
      "Run 'hermesos-update' to get the newest version."
  fi

  if [ "$id" != "ubuntu" ]; then
    refuse "this isn't Ubuntu." \
      "I found '$id'. HermesOS is built on Ubuntu Server 24.04, and I haven't been tested anywhere else. Installing anyway could leave you with a machine that half-works, which is worse than not installing at all." \
      "Install Ubuntu Server 24.04 first, or use the HermesOS disc image instead."
  fi

  if [ "$ver" != "24.04" ]; then
    refuse "this is Ubuntu $ver, not 24.04." \
      "HermesOS only supports 24.04 (the long-term-support release). Other versions have different system tools, and I'd likely break something." \
      "Upgrade to 24.04, or use the HermesOS disc image on a spare machine."
  fi

  if [ "$ram" -lt "$MIN_RAM_GB" ]; then
    refuse "there isn't enough memory." \
      "This machine has ${ram} GB. Even the smallest AI model needs about ${MIN_RAM_GB} GB to answer without long pauses, and I'd rather refuse than give you something that feels broken." \
      "Try a machine with ${MIN_RAM_GB} GB or more."
  fi

  if [ "$free" -lt "$MIN_FREE_GB" ]; then
    refuse "there isn't enough disk space." \
      "There's ${free} GB free and I need about ${MIN_FREE_GB} GB — most of that is the AI model itself." \
      "Free up some space and run this again."
  fi

  if ! is_root && [ "$PREFLIGHT_ONLY" -eq 0 ]; then
    refuse "I need administrator permission." \
      "Installing system software requires it. 'sudo' is how you grant that on Ubuntu." \
      "Run the same command again with 'sudo' in front of it."
  fi
  return 0
}

# ── the plan screen ─────────────────────────────────────────────────────
plan() {
  local fs; fs=$(fstype)
  say ""
  say "  Here's what I'm about to do to this computer."
  say ""
  say "  I WILL ADD"
  say "    · Ollama — runs the AI locally            (~120 MB)"
  say "    · Hermes Agent — the assistant itself      (~90 MB)"
  say "    · HermesOS safety tools                    (~15 MB)"
  say ""
  say "  I WILL CHANGE"
  say "    · Your login: you'll land in a conversation instead"
  say "      of a command prompt."
  say "      (Type !shell any time for the normal terminal.)"
  say "    · Add one system user called \"hermes\", with no"
  say "      admin rights."
  say ""
  say "  I WILL NOT"
  say "    · Touch any of your files"
  say "    · Remove or upgrade anything you already have"
  say "    · Change your password or your account"
  say "    · Send anything over the internet except the"
  say "      downloads listed above"
  say ""
  say "  IF YOU CHANGE YOUR MIND"
  say "    Run  hermesos-uninstall  and everything above is"
  say "    reversed. Your files are untouched either way."
  rule

  if [ "$fs" != "btrfs" ]; then
    say ""
    say "  One thing worth knowing."
    say ""
    say "  Your disk uses a format called $fs. I can still make"
    say "  restore points, using a tool called Timeshift — but they"
    say "  take a few minutes instead of a few seconds."
    say ""
    say "  This is fine. It just means \"undo that\" is slower here."
    say "  A fresh install from the HermesOS disc gets the fast kind."
    rule
  fi

  say ""
  say "  About 4 minutes, plus the model download later."
  say ""
}

confirm() {
  [ "$ASSUME_YES" -eq 1 ] && return 0
  local reply
  printf '  Type  yes  to continue, or press Ctrl-C to stop.  '
  read -r reply || { say ""; say "  Stopped. Nothing was changed."; exit 130; }
  if [ "$reply" != "yes" ]; then
    say ""
    say "  Stopped. Nothing was changed — your computer is exactly"
    say "  as it was."
    exit 0
  fi
}

main() {
  preflight
  if [ "$PREFLIGHT_ONLY" -eq 1 ]; then
    say "  This machine can run HermesOS."
    say "    Ubuntu $(os_ver) · $(ram_gb) GB memory · $(free_gb) GB free · $(fstype)"
    exit 0
  fi
  plan
  if [ "$DRY_RUN" -eq 1 ]; then
    say "  (Dry run — nothing was changed.)"
    exit 0
  fi
  confirm
  say ""
  say "  Installing…"
  say "  [ install steps land in a later commit ]"
}

main
