"""UX-8 proof: the update check — docuchat's ONE deliberate non-loopback call.

Guardrails under test: lazy (never at import/startup — the answer path's SC-6
loopback posture is untouched), toggleable off via the profile (off = zero
network attempts), cached, silent on failure, and honest version comparison.
The network fetcher is monkeypatched throughout — this test makes no real calls.
"""

import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import catalog  # noqa: E402
import updates  # noqa: E402
import api  # noqa: E402

client = TestClient(api.app)


class TestVersionParse(unittest.TestCase):
    def test_parse_and_compare(self):
        p = updates.parse_version
        self.assertEqual(p("v1.2.3"), (1, 2, 3))
        self.assertEqual(p("0.2.0-dev"), (0, 2, 0))
        self.assertEqual(p(""), (0, 0, 0))
        self.assertEqual(p("2"), (2, 0, 0))
        self.assertGreater(p("v0.3.0"), p("0.2.0-dev"))
        self.assertFalse(p("v0.1.0") > p("0.2.0-dev"))


class TestUpdateCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._cat, catalog.DEFAULT_DB = catalog.DEFAULT_DB, self.tmp / "cat.db"
        self.calls = []
        self._fetch = updates._fetch_latest
        updates._fetch_latest = lambda timeout=5: self.calls.append(1) or "v9.9.9"
        updates._cache.update({"checked_at": 0.0, "latest": None})

    def tearDown(self):
        catalog.DEFAULT_DB = self._cat
        updates._fetch_latest = self._fetch
        updates._cache.update({"checked_at": 0.0, "latest": None})

    def test_available_when_latest_newer_and_cached(self):
        s = updates.status()
        self.assertTrue(s["update_available"])
        self.assertEqual(s["latest"], "v9.9.9")
        updates.status()
        self.assertEqual(len(self.calls), 1)     # 24h cache: one fetch only

    def test_toggle_off_means_zero_network(self):
        catalog.set_profile({"update_check": False})
        s = updates.status()
        self.assertFalse(s["enabled"])
        self.assertFalse(s["update_available"])
        self.assertEqual(self.calls, [])         # no fetch attempted at all

    def test_failure_is_silent(self):
        def boom(timeout=5):
            raise OSError("no network")
        updates._fetch_latest = boom
        s = updates.status()
        self.assertFalse(s["update_available"])
        self.assertIsNone(s["latest"])

    def test_route_shape(self):
        r = client.get("/updates/status")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        for key in ("current", "enabled", "latest", "update_available"):
            self.assertIn(key, body)

    def test_never_checks_at_startup(self):
        # importing api / starting the app must not trigger the fetcher — the check
        # is lazy (UI-polled). Startup hooks are inspected by name.
        names = [f.__name__ for f in
                 [r for r in api.app.router.on_startup]]
        self.assertNotIn("update", " ".join(names).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
