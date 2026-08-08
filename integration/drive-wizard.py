#!/usr/bin/env python3
"""drive-wizard.py — blind timed driver. Sends the exact sequence with generous
waits. Crucially, after the download screen it WAITS (the download runs in the
background; the wizard advances once it finishes or is skipped) before sending
the final Enter. Run on the Mac while the VM is up."""
import socket, time, sys

HOST, PORT = "127.0.0.1", 9999
NAME = sys.argv[1] if len(sys.argv) > 1 else "Jose"
PASSWORD = "correct-horse-battery"

def main():
    s = socket.create_connection((HOST, PORT), timeout=15)
    time.sleep(3)
    def key(b, d=1.3):
        s.sendall(b); time.sleep(d)
    def type_text(t, d=0.1):
        for c in t.encode():
            s.sendall(bytes([c])); time.sleep(d)
    for _ in range(4): key(b"\r", 1.6)      # ready/hello/lang/time
    type_text(NAME); key(b"\r")             # name
    type_text(PASSWORD); key(b"\r")         # password
    key(b"\r", 1.6)                         # brain -> choose
    key(b"\x1b", 1.6)                       # download -> skip (Esc)
    time.sleep(20)                          # let the wizard advance past download
    key(b"\r", 2.0)                         # first conversation -> finish
    for _ in range(4): key(b"\r", 1.2)      # flush
    s.close()
    print("driven")

if __name__ == "__main__":
    main()
