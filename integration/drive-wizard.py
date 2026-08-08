#!/usr/bin/env python3
"""drive-wizard.py — blind timed driver for the HermesOS first-boot wizard over
the QEMU TCP serial (127.0.0.1:9999). Sends the exact key sequence with
generous waits; does not read the screen (the serial console does not redraw on a
passive read, so screen-state detection is unreliable). Run on the Mac WHILE the
VM is booted:

    bash boot-hermesos-mac.sh
    python3 drive-wizard.py [Name]      # in another terminal
    pkill -TERM -f qemu-system-aarch64   # graceful stop (flushes disk)

On a lost connection (VM already gone) it prints a clear message and exits
instead of throwing.
"""
import socket, time, sys

HOST, PORT = "127.0.0.1", 9999
NAME = sys.argv[1] if len(sys.argv) > 1 else "Jose"
PASSWORD = "correct-horse-battery"


def main():
    try:
        s = socket.create_connection((HOST, PORT), timeout=15)
    except OSError as e:
        print(f"cannot connect to {HOST}:{PORT} — is the VM booted? ({e})")
        return
    alive = True

    def key(b, d=1.3):
        nonlocal alive
        if not alive:
            return
        try:
            s.sendall(b)
        except OSError as e:
            print(f"lost connection to VM ({e}) — stopping driver")
            alive = False
            return
        time.sleep(d)

    def type_text(t, d=0.08):
        nonlocal alive
        for c in t.encode():
            if not alive:
                return
            try:
                s.sendall(bytes([c]))
            except OSError as e:
                print(f"lost connection to VM ({e}) — stopping driver")
                alive = False
                return
            time.sleep(d)

    time.sleep(3)
    for _ in range(4): key(b"\r", 1.6)      # ready / hello / language / time
    type_text(NAME); key(b"\r")             # name
    type_text(PASSWORD); key(b"\r")         # password
    key(b"\r", 1.6)                         # brain -> choose Balanced
    key(b"\x1b", 1.6)                       # download -> skip (Esc)
    time.sleep(20)                          # let the wizard advance past download
    key(b"\r", 2.0)                         # first conversation -> finish
    for _ in range(4): key(b"\r", 1.2)      # flush trailing screens
    if alive:
        s.close()
    print("driven" if alive else "driver stopped (VM connection lost)")


if __name__ == "__main__":
    main()
