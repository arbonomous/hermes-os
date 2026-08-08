#!/usr/bin/env python3
"""drive-console.py — drive the HermesOS first-boot wizard over the QEMU serial
TCP socket (127.0.0.1:9999) by writing RAW bytes (no telnet negotiation, which
the raw TUI can't parse). Each key is sent a few times so a lost byte can't
stall the wizard. Run inside the hermesos VM (root not required — serial is
127.0.0.1).

Walkthrough: ret(boot) -> ret(hello) -> ret(language) -> ret(time)
-> type NAME -> ret -> type PASSWORD -> ret -> ret(brain) -> esc(download)
-> ret(first conversation).
"""
import socket, time, sys

HOST, PORT = "127.0.0.1", 9999
SERIAL = "/tmp/hermesos-serial.log"
NAME = sys.argv[1] if len(sys.argv) > 1 else "Sam"
PASSWORD = "correct-horse-battery"


def connect(retries=40, delay=2):
    last = None
    for _ in range(retries):
        try:
            return socket.create_connection((HOST, PORT), timeout=15)
        except OSError as e:
            last = e
            time.sleep(delay)
    raise last


def key(s, b: bytes, times=3, gap=0.4):
    for _ in range(times):
        try:
            s.sendall(b)
        except OSError:
            pass
        time.sleep(gap)


def type_text(s, text: str):
    for ch in text:
        try:
            s.sendall(ch.encode())
        except OSError:
            pass
        time.sleep(0.12)


def serial_has(sub: str) -> bool:
    try:
        with open(SERIAL, "r", errors="replace") as fh:
            return sub in fh.read()
    except OSError:
        return False


def main():
    print("connecting to serial…")
    s = connect()
    print("connected")
    # Settle until the first wizard screen is up.
    for _ in range(30):
        if serial_has("press Enter when you"):
            break
        time.sleep(1)
    else:
        print("WARN: first screen not seen")

    key(s, b"\r")                 # boot
    time.sleep(1.0)
    key(s, b"\r")                 # hello
    time.sleep(1.0)
    key(s, b"\r")                 # language (en)
    time.sleep(1.0)
    key(s, b"\r")                 # time (detected)
    time.sleep(1.0)
    type_text(s, NAME)            # account name
    time.sleep(0.6)
    key(s, b"\r")                 # confirm name
    time.sleep(1.0)
    type_text(s, PASSWORD)        # password
    time.sleep(0.6)
    key(s, b"\r")                 # confirm password
    time.sleep(1.0)
    key(s, b"\r")                 # brain (Balanced)
    time.sleep(1.0)
    key(s, b"\x1b")               # download -> Esc skip
    time.sleep(1.0)
    key(s, b"\r")                 # first conversation -> finish
    time.sleep(2.0)
    for _ in range(3):
        key(s, b"\r", times=1)
        time.sleep(1.0)
    s.close()
    print("DRIVEN: sent full walkthrough over raw serial")


if __name__ == "__main__":
    main()
