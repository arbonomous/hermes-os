#!/bin/bash
# boot-hermesos-mac.sh — boot the HermesOS image directly on the Mac with QEMU.
# Runs inside an isolated VM (not bare metal). The first-boot wizard is on a
# TCP serial so YOU can drive it live:  nc 127.0.0.1 9999
# Stop it with:  pkill -TERM -f qemu-system-aarch64   (flushes disk writes)
set -euo pipefail

# clean serial transcript so each run is a single, unambiguous boot
rm -f /tmp/hermesos-serial.log

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMG="$DIR/hermesos.qcow2"
KERNEL="$DIR/hermesos-vmlinuz"
INITRD="$DIR/hermesos-initrd"

if [ ! -f "$IMG" ] || [ ! -f "$KERNEL" ] || [ ! -f "$INITRD" ]; then
  echo "ERROR: missing $IMG / $KERNEL / $INITRD" >&2
  exit 1
fi

echo "==> launching HermesOS in QEMU (isolated VM on your Mac)"
echo "    DRIVE IT LIVE:  nc 127.0.0.1 9999"
echo "    graceful stop:  pkill -TERM -f qemu-system-aarch64   (flushes the disk)"
echo "    (your Mac disk is untouched — HermesOS lives in $IMG)"
echo

exec qemu-system-aarch64 \
  -machine virt -cpu cortex-a57 -smp 2 -m 2048 \
  -kernel "$KERNEL" -initrd "$INITRD" \
  -append "root=/dev/vda1 rw earlycon=pl011,0x9000000 rootdelay=5" \
  -drive file="$IMG",format=qcow2,if=none,id=disk,cache=none,discard=unmap -device virtio-blk-device,drive=disk \
  -netdev user,id=net0 -device virtio-net-device,netdev=net0 \
  -nographic \
  -chardev socket,id=ser,host=127.0.0.1,port=9999,server=on,wait=off,logfile=/tmp/hermesos-serial.log,logappend=on \
  -serial chardev:ser
