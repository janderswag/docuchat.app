"""macOS desktop launcher (D-58 v1, Phase A) — open Legal Document Chat in a native window.

Wraps the EXISTING FastAPI app (pipeline/api.py) — it does not touch the pipeline or the
citation verifier. It:
  1. pre-kills anything stuck on the port (so a stale server can't block launch),
  2. starts the FastAPI server as a CHILD process (handle held for clean shutdown),
  3. health-checks 127.0.0.1:8000,
  4. opens the first-run wizard (/setup, which drops into /app when ready) in a pywebview
     window,
  5. kills the child server on quit — whether the window is closed, the process exits
     normally, OR the launcher is hard-killed via SIGTERM/SIGINT (no orphaned uvicorn).

Loopback-only (the server binds 127.0.0.1, never 0.0.0.0); no telemetry; no auto-update.
Run locally:  python desktop/launcher.py
The pywebview import is deferred into main() so the helpers are importable/testable headless.
"""

import atexit
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"          # loopback only — never 0.0.0.0
DEFAULT_PORT = 8000
PIPELINE_DIR = Path(__file__).resolve().parent.parent / "pipeline"


def port_in_use(port, host=HOST):
    """True if something is accepting connections on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def listening_pids(port):
    """PIDs LISTENing on ``port`` (macOS/BSD lsof). Empty if none / lsof unavailable."""
    try:
        out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                             capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [int(p) for p in out.stdout.split() if p.strip().isdigit()]


def free_port(port):
    """Pre-kill any process LISTENing on ``port`` (TERM, then KILL stragglers) so a stale
    server can't block launch. Returns the number of processes signaled."""
    pids = listening_pids(port)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if pids:
        for _ in range(20):
            if not listening_pids(port):
                break
            time.sleep(0.1)
        for pid in listening_pids(port):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    return len(pids)


def start_server(host=HOST, port=DEFAULT_PORT):
    """Start the FastAPI app as a child uvicorn process (loopback only); return the Popen.
    The caller MUST stop_server() it on exit (handle held — no orphaned server).

    ``start_new_session=True`` puts the child in its OWN process group/session, so (a) a
    terminal Ctrl-C aimed at the launcher's group doesn't race-kill the child before our
    handler runs, and (b) stop_server() can reap the whole group (uvicorn + any workers)."""
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app",
         "--host", host, "--port", str(port), "--log-level", "warning"],
        cwd=str(PIPELINE_DIR),
        start_new_session=True,
    )


def wait_healthy(port=DEFAULT_PORT, host=HOST, timeout=40.0):
    """Poll GET /health until 200 (True) or ``timeout`` (False)."""
    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def _signal_group(proc, sig):
    """Send ``sig`` to the child's whole process group (start_new_session leader); fall
    back to signalling just the child if the group can't be resolved."""
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.send_signal(sig)
        except (ProcessLookupError, OSError):
            pass


def stop_server(proc, timeout=8.0):
    """Terminate the child server's whole process group, escalating to KILL; idempotent and
    safe to call from a signal handler, atexit, and the main finally — never leaves an
    orphan holding the port."""
    if proc is None or proc.poll() is not None:
        return
    _signal_group(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _signal_group(proc, signal.SIGKILL)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            pass


def install_cleanup(proc):
    """Guarantee the child server is reaped however the launcher exits — window close
    (main's finally), normal exit (atexit), OR a hard kill via SIGTERM/SIGINT (handlers).
    This closes the D-59 yellow: a killed launcher can no longer orphan uvicorn on port
    8000. (SIGKILL is uncatchable by design; free_port() on the next launch self-heals it.)"""
    atexit.register(stop_server, proc)

    def _handler(signum, _frame):
        stop_server(proc)
        # re-raise the default disposition so the exit status reflects the signal
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError):
            pass  # not on the main thread / unsupported — atexit + finally still cover it
    return _handler


def main(port=DEFAULT_PORT):
    free_port(port)                       # pre-kill a stale server holding the port
    proc = start_server(port=port)
    install_cleanup(proc)                 # reap the child on window-close, exit, OR kill
    try:
        if not wait_healthy(port=port):
            stop_server(proc)
            print("Server did not become healthy on "
                  f"http://{HOST}:{port}", file=sys.stderr)
            return 1
        import webview  # deferred: needs a display; keep the helpers headless-importable
        webview.create_window(
            "Legal Document Chat",
            f"http://{HOST}:{port}/setup",   # wizard first; it redirects to /app when ready
            width=1200, height=820, min_size=(900, 640),
        )
        webview.start()                   # blocks until the window is closed
        return 0
    finally:
        stop_server(proc)                 # kill the child server on quit (no orphan)


if __name__ == "__main__":
    raise SystemExit(main())
