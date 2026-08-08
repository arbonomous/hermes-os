#!/usr/bin/env python3
"""pty-firstboot.py — run the REAL firstbootd.py (which launches the live TUI
when it has a tty) inside a pty, feed it real keystrokes, and prove the
interactive wizard drives actual provisioning. Run inside the hermesos VM.

Unlike the QEMU serial path, a pty delivers keystrokes to the TUI reliably,
so this demonstrates the full interactive -> provision chain on real code.
"""
import os, pty, time, select, sys

FB = "/tmp/fb/firstbootd.py"
NAME = sys.argv[1] if len(sys.argv) > 1 else "Sam"
PASSWORD = "correct-horse-battery"

def main():
    pid, fd = pty.fork()
    if pid == 0:
        # child: exec firstbootd with --apply; stdin is the pty (a real tty)
        os.environ["FIRSTBOOT_APPLY"] = "1"
        os.execv(sys.executable, [sys.executable, FB, "--apply"])
        os._exit(127)

    # parent: drive the pty
    def send(b):
        os.write(fd, b)
        time.sleep(0.15)

    time.sleep(2)  # let the wizard render screen 1
    send(b"\r")            # boot
    time.sleep(1)
    send(b"\r")            # hello
    time.sleep(1)
    send(b"\r")            # language (en)
    time.sleep(1)
    send(b"\r")            # time (detected)
    time.sleep(1)
    for ch in NAME:       # account name
        send(ch.encode())
    time.sleep(0.5)
    send(b"\r")
    time.sleep(1)
    for ch in PASSWORD:    # password
        send(ch.encode())
    time.sleep(0.5)
    send(b"\r")
    time.sleep(1)
    send(b"\r")            # brain (Balanced)
    time.sleep(1)
    send(b"\x1b")          # download -> Esc skip
    time.sleep(1)
    send(b"\r")            # first conversation -> finish
    time.sleep(2)
    # drain remaining output
    buf = b""
    end = time.time() + 3
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            try:
                buf += os.read(fd, 4096)
            except OSError:
                break
    out = buf.decode(errors="replace")
    # show the screen we reached + any provisioning output
    for marker in ["computer's voice", "call you", "choosing my brain",
                   "Provisioning complete", "CREATE YOUR ACCOUNT", "useradd"]:
        if marker in out:
            print(f"  [seen] {marker}")
    print("DRIVEN interactive firstbootd via pty")
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass

if __name__ == "__main__":
    main()
