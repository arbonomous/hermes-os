#!/usr/bin/env python3
"""End-to-end arrow-key verification: connect to the live HermesOS wizard
serial, drive it, and READ the screen (from the socket) to confirm the
highlighted (▸) option actually moves when arrows are pressed.

This is the real proof: it does not assume arrows work — it observes the
rendered screen after each keystroke.
"""
import socket, time, sys, re

HOST, PORT = "127.0.0.1", 9999

def connect():
    s = socket.create_connection((HOST, PORT), timeout=20)
    s.settimeout(1.0)
    return s

def recv_until(s, marker, timeout=20.0):
    """Drain until `marker` (bytes) appears in the stream, or timeout."""
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        try:
            d = s.recv(65536)
        except socket.timeout:
            if marker in buf:
                return buf
            continue
        except OSError:
            return buf
        if not d:
            return buf
        buf += d
        if marker in buf:
            return buf
    return buf

def screen_after(s, key: bytes, label: str):
    """Send `key`, then read the screen and report which option is ▸-highlighted."""
    s.sendall(key)
    time.sleep(1.2)
    buf = b""
    end = time.time() + 3.0
    while time.time() < end:
        try:
            d = s.recv(65536)
        except socket.timeout:
            break
        except OSError:
            break
        if not d:
            break
        buf += d
    text = buf.decode("utf-8", "replace")
    # find the ▸-highlighted label on the current screen
    m = re.findall(r"▸\s*([A-Za-z].*?)\s*(?:\[|│)", text)
    highlighted = m[-1] if m else None
    print(f"  after {label}: highlighted = {highlighted!r}")
    return highlighted, text

def main():
    s = connect()
    # 1) wait for the wizard to start
    boot = recv_until(s, b"=== HermesOS first boot ===", timeout=25)
    if b"=== HermesOS first boot ===" not in boot:
        print("FAIL: wizard never started (no '=== HermesOS first boot ===')")
        s.close(); sys.exit(1)
    # 2) wait for the boot screen ("press Enter when you're ready")
    boot = recv_until(s, b"press Enter when you're ready", timeout=10)
    if b"press Enter when you're ready" not in boot:
        print("FAIL: boot screen not shown")
        s.close(); sys.exit(1)
    print("  boot screen seen; pressing Enter -> hello")
    # 3) Enter boot->hello; the returned screen text should contain the hello
    #    screen ("Press Enter to begin").
    _, hello_text = screen_after(s, b"\r", "Enter (boot->hello)")
    if "Press Enter to begin" not in hello_text:
        print("FAIL: hello screen not shown after Enter (got end of buffer)")
        s.close(); sys.exit(1)
    print("  hello screen seen; pressing Enter -> language")
    lang0, _ = screen_after(s, b"\r", "Enter (hello->language)")
    if lang0 is None:
        print("FAIL: did not reach a choice screen after Enter")
        s.close(); sys.exit(1)
    print(f"  on language screen, initial highlight = {lang0!r}")
    # 4) Down -> should move highlight
    down, _ = screen_after(s, b"\x1b[B", "Down")
    # 5) Down again
    down2, _ = screen_after(s, b"\x1b[B", "Down")
    # 6) Up -> should move back
    up, _ = screen_after(s, b"\x1b[A", "Up")

    results = []
    results.append(("reached language screen", lang0 is not None))
    results.append(("Down moved highlight", down is not None and down != lang0))
    results.append(("Up restored/changed highlight", up is not None and up != down2))
    moved = down != lang0
    print(f"\n  initial={lang0!r}  after Down={down!r}  after Down2={down2!r}  after Up={up!r}")
    print(f"  ARROWS WORK: {moved}")
    s.close()
    ok = all(r[1] for r in results)
    print(f"\n{'='*46}\n{'PASS' if ok else 'FAIL'} — arrows {'moved selection' if ok else 'did NOT move selection'}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
