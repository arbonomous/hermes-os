#!/usr/bin/env bash
# Run the btrfs integration test inside a Linux VM.
#
#   ./integration/run.sh
#
# Boots the VM if it isn't running, then runs the test as root inside it.
# Nothing touches the host filesystem.

set -euo pipefail

VM=hermesos
HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v limactl >/dev/null; then
  echo "Lima isn't installed. Install it with:"
  echo "    brew install lima"
  exit 1
fi

status=$(limactl list --format '{{.Status}}' "$VM" 2>/dev/null || true)

if [ -z "$status" ]; then
  echo "Creating the $VM VM (first run downloads Ubuntu, a few minutes)…"
  limactl start --name="$VM" --tty=false "$HERE/lima-hermesos.yaml"
elif [ "$status" != "Running" ]; then
  echo "Starting the $VM VM…"
  limactl start --tty=false "$VM"
fi

echo
echo "Running the btrfs round trip inside Linux…"
echo

limactl shell "$VM" sudo python3 /hermes-os/integration/test_btrfs_roundtrip.py
