"""Task 7 proof: read-only system/status for the Settings view + privacy badge.

GET /settings/status reports the pinned models, the loopback bind, loopback-only egress
posture (DERIVED from the real Ollama URL, not a blind hardcode), and integer KB store
counts — and exposes NO secret or filesystem path."""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import api  # noqa: E402

client = TestClient(api.app)
APP_JS = (PIPELINE_DIR / "static" / "app.js").read_text()


class TestSettingsStatus(unittest.TestCase):
    def test_status_is_truthful(self):
        s = client.get("/settings/status").json()
        self.assertEqual(s["bind"], "127.0.0.1")
        self.assertEqual(s["egress"], "loopback-only")
        self.assertEqual(s["models"]["chat"], "qwen3:14b")
        self.assertEqual(s["models"]["embed"], "bge-m3")
        self.assertIn("127.0.0.1:11434", s["ollama"])
        self.assertIsInstance(s["stores"]["kb_docs"], int)
        self.assertIsInstance(s["stores"]["kb_chunks"], int)

    def test_status_leaks_no_secret_or_path(self):
        blob = json.dumps(client.get("/settings/status").json())
        self.assertNotIn("/Users/", blob)
        self.assertNotIn(".db", blob)
        self.assertNotIn("key", blob.lower())
        self.assertNotIn(".lancedb", blob)


class TestTimeMachineFailureSurfaced(unittest.TestCase):
    """Trust fix (gaps-audit "silent privacy-feature failure"): data_protection's
    startup exclusion attempt only ever logs a warning on failure (api.py:158-165) —
    /settings/status must surface it as a real signal, not just the raw per-store
    dump nobody but a developer can read."""

    def test_false_when_everything_excluded(self):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch.object(api.app.state, "data_protection",
                               {"search index": "time-machine-excluded+spotlight-marker",
                                "catalog database": "absent"}, create=True):
            s = client.get("/settings/status").json()
        self.assertFalse(s["hardening"]["time_machine_failed"])

    def test_true_when_a_store_could_not_be_excluded(self):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch.object(api.app.state, "data_protection",
                               {"search index": "time-machine-excluded",
                                "catalog database": "tmutil-unavailable"}, create=True):
            s = client.get("/settings/status").json()
        self.assertTrue(s["hardening"]["time_machine_failed"])

    def test_never_a_failure_off_macos(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch.object(api.app.state, "data_protection",
                               {"search index": "tmutil-unavailable"}, create=True):
            s = client.get("/settings/status").json()
        self.assertFalse(s["hardening"]["time_machine_failed"])


class TestTimeMachineFailureUI(unittest.TestCase):
    """Static assertions: one honest, quiet-on-success line in Settings -> System,
    informational (not alarm-red) styling."""

    def test_message_and_gate_present(self):
        pane = APP_JS[APP_JS.index("async function renderSystemPane"):
                      APP_JS.index("async function renderSystemPane") + 3000]
        self.assertIn("time_machine_failed", pane)
        self.assertIn("Could not exclude the data folder from Time Machine", pane)
        self.assertIn("Your encrypted data may be included in backups.", pane)

    def test_uses_informational_not_alarm_styling(self):
        pane = APP_JS[APP_JS.index("async function renderSystemPane"):
                      APP_JS.index("async function renderSystemPane") + 3000]
        line = pane[pane.index("time_machine_failed"):]
        self.assertIn("panel muted", line[:200])


if __name__ == "__main__":
    unittest.main(verbosity=2)
