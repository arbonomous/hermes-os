#!/usr/bin/env python3
"""pty-firstboot-debug.py — same as pty-firstboot but dumps the FULL pty output
to /tmp/fb-out.txt so we can see any traceback from firstbootd."""
import os, pty, time, select, sys

FB = "/tmp/fb/firstbootd.py"
NAME = sys.argv[1] if len(sys.argv) > 1 else "Sam"
PASSWORD = "correct-horse-battery"

pid, fd = pty.fork()
if pid == 0:
    os.environ["FIRSTBOOT_APPLY"] = "1"
    os.execv(sys.executable, [sys.executable, FB, "--apply"])
    os._exit(127)

def send(b):
    os.write(fd, b); time.sleep(0.15)

time.sleep(2)
send(b"\r"); time.sleep(1)
send(b"\r"); time.sleep(1)
send(b"\r"); time.sleep(1)
send(b"\r"); time.sleep(1)
for ch in NAME: send(ch.encode())
time.sleep(0.5); send(b"\r"); time.sleep(1)
for ch in PASSWORD: send(ch.encode())
time.sleep(0.5); send(b"\r"); time.sleep(1)
send(b"\r"); time.sleep(1)
send(b"\x1b"); time.sleep(1)
send(b"\r"); time.sleep(2)

buf = b""
end = time.time() + 3
while time.time() < end:
    r, _, _ = select.select([fd], [], [], 0.5)
    if r:
        try: buf += os.read(fd, 4096)
        except OSError: break
with open("/tmp/fb-out.txt", "wb") as fh:
    fh.write(buf)
print("wrote /tmp/fb-out.txt (", len(buf), "bytes )")
try: os.waitpid(pid, 0)
except ChildProcessError: pass
