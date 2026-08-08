#!/bin/bash
# boot-hermesos-qemu.sh — boot the HermesOS image under QEMU (aarch64) inside
# the hermesos Lima VM. Uses the kernel/initrd extracted from the image (GRUB
# EFI install was skipped), serial console on TCP 127.0.0.1:9999 so we can
# watch it come up. Runs ONLY inside the throwaway VM.
set -euo pipefail

IMG=/var/lib/hermesos/hermesos.img
MNT=/mnt/hermesos-boot
KERNEL=/tmp/hermesos-vmlinuz
INITRD=/tmp/hermesos-initrd

echo "==> extracting kernel + initrd from image"
LOOP=$(sudo losetup --find --show --partscan "$IMG")
sudo mkdir -p "$MNT"
sudo mount "${LOOP}p1" "$MNT"
VMLINUZ=$(ls "$MNT"/boot/vmlinuz-* 2>/dev/null | head -1)
INITRD_SRC=$(ls "$MNT"/boot/initrd.img-* 2>/dev/null | grep -v '\.old$' | head -1)
sudo cp "$VMLINUZ" "$KERNEL"
sudo cp "$INITRD_SRC" "$INITRD"
sudo umount "$MNT"
sudo losetup -d "$LOOP"
echo "    kernel=$VMLINUZ"

echo "==> launching QEMU (serial on tcp:127.0.0.1:9999)"
echo "    connect with:  nc -v 127.0.0.1 9999   (or socat - TCP:127.0.0.1:9999)"
# -nographic + -serial tcp lets us stream the boot. -daemonize would detach;
# we run foreground so it dies with the shell.
sudo qemu-system-aarch64 \
  -machine virt -cpu cortex-a57 -smp 2 -m 2048 \
  -kernel "$KERNEL" -initrd "$INITRD" \
  -append "console=ttyAMA0,115200 root=/dev/vda1 rw earlycon=pl011,0x9000000 rootdelay=5" \
  -drive file="$IMG",format=raw,if=none,id=disk -device virtio-blk-device,drive=disk \
  -netdev user,id=net0 -device virtio-net-device,netdev=net0 \
  -nographic -serial file:/tmp/hermesos-serial.log -monitor none
echo "==> boot started. Serial log: /tmp/hermesos-serial.log"
echo "    tail it:  sudo tail -f /tmp/hermesos-serial.log"
