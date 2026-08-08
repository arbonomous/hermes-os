#!/bin/bash
# boot-hermesos-qemu.sh — boot the HermesOS image under QEMU (aarch64) inside
# the hermesos Lima VM. Uses the kernel/initrd extracted from the image (GRUB
# EFI install was skipped). The boot console is captured to a file
# (/tmp/hermesos-serial.log) and a QEMU monitor socket (/tmp/qemu-mon.sock)
# lets a driver inject keystrokes via `sendkey` so the first-boot wizard can
# be driven live and observed.
set -euo pipefail

IMG=/var/lib/hermesos/hermesos.img
MNT=/mnt/hermesos-boot
KERNEL=/tmp/hermesos-vmlinuz
INITRD=/tmp/hermesos-initrd

sudo mkdir -p "$MNT"
LOOP=$(sudo losetup --find --show --partscan "$IMG")
sudo mount "${LOOP}p1" "$MNT"

VMLINUZ=$(ls "$MNT"/boot/vmlinuz-* 2>/dev/null | head -1)
INITRD_SRC=$(ls "$MNT"/boot/initrd.img-* 2>/dev/null | grep -v '\.old$' | head -1)
sudo cp "$VMLINUZ" "$KERNEL"
sudo cp "$INITRD_SRC" "$INITRD"
sudo umount "$MNT"
sudo losetup -d "$LOOP"

echo "==> launching QEMU"
echo "    console log:  sudo tail -f /tmp/hermesos-serial.log"
echo "    drive with:   python3 /tmp/drive-console.py <name>"

sudo qemu-system-aarch64 \
  -machine virt -cpu cortex-a57 -smp 2 -m 2048 \
  -kernel "$KERNEL" -initrd "$INITRD" \
  -append "console=ttyAMA0,115200 root=/dev/vda1 rw earlycon=pl011,0x9000000 rootdelay=5" \
  -drive file="$IMG",format=raw,if=none,id=disk -device virtio-blk-device,drive=disk \
  -netdev user,id=net0 -device virtio-net-device,netdev=net0 \
  -nographic -serial tcp:127.0.0.1:9999,server,nowait \
  -monitor unix:/tmp/qemu-mon.sock,server,nowait
