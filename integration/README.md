# integration/ — building a bootable HermesOS disk image

This builds a **real HermesOS disk image** from the repo and boots it under
QEMU — a separate machine running HermesOS, used to watch first boot work
end-to-end. Everything runs **inside the `hermesos` Lima VM** (a throwaway
Ubuntu box), so your Mac is never touched.

## What you get
`build-hermesos-image.sh` produces `/var/lib/hermesos/hermesos.img`:
a minimal Ubuntu 24.04 rootfs with the `firstboot/` layer installed,
`firstbootd.service` enabled, and `/etc/hermesos/.setup-pending` set. On
first boot the service runs the live wizard (`tui.py`) and provisions the
machine (creates the `hermes` user, etc.), then clears the pending flag.

## Steps (all inside the hermesos VM)
```bash
# one-time: install QEMU + debootstrap in the VM
limactl shell hermesos -- bash -c 'sudo apt-get update -qq && \
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  debootstrap qemu-system-arm qemu-utils'

# build the image
limactl shell hermesos -- bash -c 'sudo bash /tmp/build-hermesos-image.sh'

# boot it under QEMU (serial log at /tmp/hermesos-serial.log)
limactl shell hermesos -- bash -c 'sudo bash /tmp/boot-hermesos-qemu.sh'
limactl shell hermesos -- bash -c 'sudo tail -f /tmp/hermesos-serial.log'
```

## Notes
- GRUB EFI install is skipped; the boot script extracts the kernel + initrd
  from the image and launches QEMU with `-kernel`/`-initrd` and
  `console=ttyAMA0` (the `virt` machine's UART).
- The disk shows up as `/dev/vda1` under QEMU `virt` (not `/dev/sda1`).
- `model.download` records `ok:false` on a minimal image because
  `/usr/lib/hermesos/fetch-model` isn't installed yet — that's expected and
  fails safe; it does not abort provisioning.
- Reset: `limactl delete hermesos && limactl start hermesos` (fresh VM).
