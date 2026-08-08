#!/bin/bash
# build-hermesos-image.sh — build a bootable HermesOS disk image (aarch64).
# Runs INSIDE the hermesos Lima VM (privileged first-boot boundary).
# Produces /var/lib/hermesos/hermesos.img: a minimal Ubuntu 24.04 rootfs that,
# on first boot, runs firstbootd -> the live tui.py wizard -> provisioning.
set -euo pipefail

IMG=/var/lib/hermesos/hermesos.img
SIZE_GB=8
MNT=/mnt/hermesos-build
REPO=/hermes-os

echo "==> creating image $IMG (${SIZE_GB}G)"
sudo mkdir -p /var/lib/hermesos
sudo rm -f "$IMG"
sudo qemu-img create -f raw "$IMG" "${SIZE_GB}G" >/dev/null

echo "==> loop-mounting"
LOOP=$(sudo losetup --find --show "$IMG")
echo "    loop=$LOOP"
sudo parted -s "$LOOP" mklabel msdos
sudo parted -s "$LOOP" mkpart primary ext4 1MiB 100%
PART="${LOOP}p1"
sudo mkfs.ext4 -F "$PART" >/dev/null
sudo mkdir -p "$MNT"
sudo mount "$PART" "$MNT"

echo "==> debootstrapping Ubuntu 24.04 (noble)"
sudo debootstrap --arch=arm64 --include=systemd,systemd-sysv,grub-efi-arm64,linux-generic,openssh-server,python3,locales,btrfs-progs noble "$MNT" http://ports.ubuntu.com/ubuntu-ports >/dev/null 2>&1 || {
  echo "debootstrap failed; partial log:"; tail -5 /var/log/bootstrap.log 2>/dev/null; exit 1; }

echo "==> installing HermesOS firstboot layer from $REPO"
sudo mkdir -p "$MNT/usr/lib/hermesos/firstboot"
sudo cp -r "$REPO/firstboot/wizard.py" "$REPO/firstboot/apply.py" "$REPO/firstboot/converge.py" \
          "$REPO/firstboot/firstbootd.py" "$REPO/firstboot/tui.py" \
          "$MNT/usr/lib/hermesos/firstboot/"
sudo cp "$REPO/firstboot/firstbootd.service" "$MNT/etc/systemd/system/firstbootd.service"
sudo mkdir -p "$MNT/etc/hermesos"
sudo touch "$MNT/etc/hermesos/.setup-pending"        # triggers first boot

echo "==> basic fstab + hostname"
echo "/dev/sda1 / ext4 defaults 0 1" | sudo tee "$MNT/etc/fstab" >/dev/null
echo "hermesos" | sudo tee "$MNT/etc/hostname" >/dev/null
sudo sed -i 's/^127.0.1.1.*/127.0.1.1 hermesos/' "$MNT/etc/hosts" 2>/dev/null || echo "127.0.1.1 hermesos" | sudo tee -a "$MNT/etc/hosts" >/dev/null

echo "==> enable firstboot service + serial console for QEMU viewing"
sudo ln -sf /etc/systemd/system/firstbootd.service "$MNT/etc/systemd/system/multi-user.target.wants/firstbootd.service"
echo 'GRUB_CMDLINE_LINUX="console=ttyS0"' | sudo tee -a "$MNT/etc/default/grub" >/dev/null
sudo chroot "$MNT" update-grub >/dev/null 2>&1 || echo "grub cfg warn (non-fatal if EFI missing)"

echo "==> installing GRUB to the image"
sudo grub-install --target=arm64-efi --boot-directory="$MNT/boot" --efi-directory="$MNT/boot/efi" "$LOOP" >/dev/null 2>&1 || \
  sudo grub-install --target=arm64-efi --boot-directory="$MNT/boot" --no-floppy --force "$LOOP" >/dev/null 2>&1 || echo "grub-install note (will use QEMU -kernel path if needed)"

echo "==> cleanup"
sudo umount "$MNT"
sudo losetup -d "$LOOP"
echo "==> image ready: $IMG ($(sudo du -h "$IMG" | cut -f1))"
