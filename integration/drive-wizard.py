#!/usr/bin/env python3
"""drive-wizard.py — blind timed driver for the HermesOS first-boot wizard over
the QEMU TCP serial (127.0.0.1:9999). The serial console does not redraw on a
passive read, so screen state is undetectable; this driver paces keys
sequentially with generous gaps so they land on the expected screens.

Run on the Mac WHILE the VM is booted:
    bash boot-hermesos-mac.sh
    python3 drive-wizard.py [Name]
    pkill -TERM -f qemu-system-aarch64   # graceful stop (flushes disk)

On a lost connection it prints a clear message and exits instead of throwing.
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

    def key(b, d=2.0):
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

    def type_text(t, d=0.12):
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

    # Sequential pacing: the intro is "getting ready" -> language -> time, each
    # one Enter apart. Then the name screen, where we must TYPE before Enter.
    time.sleep(10)                      # let "getting ready" appear
    key(b"\r", 3.5)                     # start wizard
    key(b"\r", 3.5)                     # language -> accept
    key(b"\r", 3.5)                     # time -> accept
    time.sleep(3.5)                     # ensure name screen is active + focused
    type_text(NAME, 0.25)               # name (slow, so each char registers)
    time.sleep(1.5)
    key(b"\r", 3.5)                     # confirm name
    time.sleep(3.5)
    type_text(PASSWORD, 0.25)           # password
    time.sleep(1.5)
    key(b"\r", 3.5)                     # confirm password
    key(b"\r", 3.5)                     # brain -> choose Balanced
    key(b"\x1b", 3.5)                   # download -> skip (Esc)
    time.sleep(22)                      # let wizard advance past download
    key(b"\r", 3.5)                     # first conversation -> finish
    for _ in range(4): key(b"\r", 1.5)  # flush trailing screens
    if alive:
        s.close()
    print("driven" if alive else "driver stopped (VM connection lost)")


if __name__ == "__main__":
    main()
