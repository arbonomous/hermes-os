#!/usr/bin/env python3
"""Drive the FULL HermesOS first-boot wizard to completion over the serial,
then let firstbootd write firstboot.plan.json + os.sync(). After a hard VM
stop we can read plan.json from the qcow2 to prove the interactive flow
produced a real, persisted plan.

Order (see firstboot/wizard.py SCREENS):
  boot -> hello -> language -> time -> account_name -> account_password
  -> brain -> download -> first_conversation -> done
"""
import socket, time, sys

HOST, PORT = "127.0.0.1", 9999

def connect():
    s = socket.create_connection((HOST, PORT), timeout=20)
    s.settimeout(1.0)
    return s

def recv_until(s, marker, timeout=25.0):
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        try:
            d = s.recv(65536)
        except socket.timeout:
            if marker in buf:
                return True
            continue
        except OSError:
            return marker in buf
        if not d:
            return marker in buf
        buf += d
        if marker in buf:
            return True
    return marker in buf

def step(s, key: bytes, marker: bytes, label: str, wait=1.4):
    s.sendall(key)
    ok = recv_until(s, marker, timeout=20.0)
    print(f"  {'OK ' if ok else '?? '} {label}  (next screen seen: {ok})")
    time.sleep(wait * 0.4)
    return ok

def main():
    s = connect()
    steps = 0
    # boot -> hello
    if not recv_until(s, b"press Enter when you're ready", 25):
        print("FAIL: boot screen never appeared"); s.close(); sys.exit(1)
    step(s, b"\r", b"Press Enter to begin", "Enter: boot->hello")
    # hello -> language
    step(s, b"\r", b"What language should I speak?", "Enter: hello->language")
    # language -> time (default English)
    step(s, b"\r", b"Where are you?", "Enter: language->time (English)")
    # time -> account_name (default detected)
    step(s, b"\r", b"What should I call you?", "Enter: time->name")
    # type name -> account_password
    for ch in b"Sam":
        s.sendall(bytes([ch])); time.sleep(0.05)
    step(s, b"\r", b"Now a password", "name 'Sam' + Enter -> password")
    # type password -> brain
    for ch in b"correct-horse-battery":
        s.sendall(bytes([ch])); time.sleep(0.03)
    step(s, b"\r", b"choosing my brain", "pw + Enter -> brain")
    # brain -> download (default Balanced)
    step(s, b"\r", b"Downloading my brain", "Enter: brain->download")
    # download -> first_conversation (Esc to skip the long download)
    step(s, b"\x1b", b"Ready. Let's try it once", "Esc: skip download -> first_convo")
    # first_conversation -> done -> provisioning
    s.sendall(b"\r"); time.sleep(2.0)
    done = recv_until(s, b"Provisioning complete", timeout=30.0)
    print(f"  {'OK ' if done else '?? '} reached 'Provisioning complete': {done}")
    steps += 1
    s.close()
    print("\nWizard driven to completion." if done else "\nWizard did NOT reach provisioning.")
    sys.exit(0 if done else 1)

if __name__ == "__main__":
    main()
