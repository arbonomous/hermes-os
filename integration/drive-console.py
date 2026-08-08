#!/usr/bin/env python3
"""drive-console.py — connect to the HermesOS QEMU console (tcp:127.0.0.1:9999),
drive the live first-boot wizard with real keystrokes, and capture frames so we
can SEE the interactive TUI in action. Run inside the hermesos VM.

Walkthrough: Enter (boot) -> Enter (hello) -> Enter (language en) -> Enter
(time London) -> type NAME -> Enter -> type PASSWORD -> Enter -> Enter (brain
Balanced) -> Esc (skip download) -> Enter (first conversation).
"""
import socket, time, sys

HOST, PORT = "127.0.0.1", 9999
NAME = sys.argv[1] if len(sys.argv) > 1 else "Sam"

def send(sock, s):
    sock.sendall(s.encode())

def frame_capture(sock, secs, tag):
    """Read whatever the guest emitted for `secs` and dump it."""
    sock.settimeout(secs)
    buf = b""
    end = time.time() + secs
    while time.time() < end:
        try:
            data = sock.recv(4096)
            if not data:
                break
            buf += data
        except socket.timeout:
            break
    txt = buf.decode(errors="replace")
    # collapse to last ~40 lines for readability
    lines = [l for l in txt.splitlines() if l.strip()]
    print(f"\n===== FRAME: {tag} =====")
    print("\n".join(lines[-40:]))

s = socket.create_connection((HOST, PORT), timeout=10)
time.sleep(1)

# boot + hello info screens
for _ in range(2):
    send(s, "\r"); time.sleep(2.5)
    frame_capture(s, 2.5, "after Enter (info)")

# language (choice) -> accept English default
send(s, "\r"); time.sleep(2.5); frame_capture(s, 2.5, "language")

# time (choice) -> accept detected
send(s, "\r"); time.sleep(2.5); frame_capture(s, 2.5, "time")

# account_name (text) -> type the name
for ch in NAME:
    send(s, ch); time.sleep(0.15)
time.sleep(0.5); frame_capture(s, 2.0, f"typed name '{NAME}'")
send(s, "\r"); time.sleep(2.5)

# account_password (password) -> type a password
for ch in "correct-horse-battery":
    send(s, ch); time.sleep(0.10)
time.sleep(0.5); frame_capture(s, 2.0, "typed password (masked)")
send(s, "\r"); time.sleep(2.5)

# brain (choice) -> accept Balanced default
send(s, "\r"); time.sleep(2.5); frame_capture(s, 2.5, "brain -> Balanced")

# download (progress) -> Esc to skip
send(s, "\x1b"); time.sleep(2.5); frame_capture(s, 2.5, "download -> Esc skip")

# first_conversation (info) -> Enter
send(s, "\r"); time.sleep(3.0); frame_capture(s, 3.0, "first conversation")

print("\n===== DONE: wizard driven interactively =====")
s.close()
