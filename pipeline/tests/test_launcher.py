"""D-58 v1 — macOS launcher lifecycle (headless; no GUI).

Proves the launcher's server lifecycle without opening a window: an unused port reads free;
start_server -> health 200 -> stop_server releases the port; free_port() kills a stale
listener (pre-kill on launch); and a SIGTERM to the launcher reaps its child uvicorn so a
hard kill cannot orphan the server on port 8000 (the D-59 yellow). The pywebview window
itself is exercised manually (`python desktop/launcher.py`).
"""

import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DESKTOP = REPO_ROOT / "desktop"
sys.path.insert(0, str(DESKTOP))
import launcher  # noqa: E402  (module under test)

PORT = 8771  # a high, unlikely-used port (NOT the app's 8000)
PORT2 = 8772  # a second port for the signal-cleanup driver


def _wait_released(port, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not launcher.port_in_use(port):
            return True
        time.sleep(0.2)
    return False


class TestLauncherLifecycle(unittest.TestCase):
    def test_unused_port_reads_free(self):
        self.assertFalse(launcher.port_in_use(PORT))
        self.assertEqual(launcher.listening_pids(PORT), [])
        self.assertEqual(launcher.free_port(PORT), 0)  # no-op when nothing is listening

    def test_start_health_stop_releases_port(self):
        proc = launcher.start_server(port=PORT)
        try:
            self.assertTrue(launcher.wait_healthy(port=PORT), "server never became healthy")
            self.assertTrue(launcher.port_in_use(PORT))
        finally:
            launcher.stop_server(proc)
        self.assertTrue(_wait_released(PORT), "port not released after stop_server")

    def test_free_port_kills_a_stale_listener(self):
        proc = launcher.start_server(port=PORT)
        try:
            self.assertTrue(launcher.wait_healthy(port=PORT))
            killed = launcher.free_port(PORT)              # pre-kill behavior
            self.assertGreaterEqual(killed, 1, "free_port did not signal the listener")
            self.assertTrue(_wait_released(PORT), "free_port left the port held")
        finally:
            launcher.stop_server(proc)


# A standalone launcher driver: starts the server, installs the signal cleanup, reports
# READY, then idles — exactly what main() does around the (GUI-only) window.
_DRIVER = textwrap.dedent("""
    import sys, time
    sys.path.insert(0, {desktop!r})
    import launcher
    proc = launcher.start_server(port={port})
    launcher.install_cleanup(proc)
    if not launcher.wait_healthy(port={port}, timeout=40):
        launcher.stop_server(proc); sys.exit(3)
    print("READY", flush=True)
    while True:
        time.sleep(0.3)
""")


class TestLauncherSignalCleanup(unittest.TestCase):
    def test_sigterm_reaps_child_no_orphan(self):
        # The launcher's child is in its own session (start_new_session); only the
        # install_cleanup SIGTERM handler reaps it. If the handler is missing/broken, the
        # grandchild uvicorn is orphaned and the port stays held -> this test fails.
        src = _DRIVER.format(desktop=str(DESKTOP), port=PORT2)
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(src)
            driver_path = f.name
        drv = subprocess.Popen([sys.executable, driver_path],
                               stdout=subprocess.PIPE, text=True)
        try:
            line = drv.stdout.readline().strip()  # blocks until READY (or EOF on failure)
            self.assertEqual(line, "READY", "driver did not bring the server up")
            self.assertTrue(launcher.port_in_use(PORT2))

            drv.send_signal(signal.SIGTERM)       # hard-kill the launcher driver
            drv.wait(timeout=20)
            self.assertTrue(_wait_released(PORT2, timeout=15),
                            "SIGTERM orphaned the child uvicorn (port still held)")
        finally:
            if drv.poll() is None:
                drv.kill()
            if drv.stdout:
                drv.stdout.close()
            launcher.free_port(PORT2)             # belt-and-suspenders
            try:
                os.unlink(driver_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
