"""M2-9 proof: the Ollama base URL is env-configurable so the containerized app can
reach the HOST Ollama via host.docker.internal:11434, WITHOUT changing Ollama's bind
(it stays on the host at 127.0.0.1:11434, D-11) and WITHOUT setting OLLAMA_HOST.

Default (no env) = http://127.0.0.1:11434 — the non-containerized path is unchanged.
`LDI_OLLAMA_URL` overrides it (compose sets it to http://host.docker.internal:11434).
Both call sites (`embed_store.embed_texts`, `answering._chat`) resolve through one
helper so there is no drift, and the var is NOT named OLLAMA_HOST (that is Ollama's
own server-bind var, which must stay unset).
"""

import os
import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))

import embed_store  # noqa: E402
import answering  # noqa: E402


class TestOllamaUrlResolution(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("LDI_OLLAMA_URL")
        os.environ.pop("LDI_OLLAMA_URL", None)

    def tearDown(self):
        os.environ.pop("LDI_OLLAMA_URL", None)
        if self._saved is not None:
            os.environ["LDI_OLLAMA_URL"] = self._saved

    def test_default_is_host_loopback(self):
        self.assertEqual(embed_store.ollama_url(), "http://127.0.0.1:11434")

    def test_env_override_points_at_host_docker_internal(self):
        os.environ["LDI_OLLAMA_URL"] = "http://host.docker.internal:11434"
        self.assertEqual(embed_store.ollama_url(), "http://host.docker.internal:11434")

    def test_resolved_at_call_time_not_import_time(self):
        # set AFTER import -> must still take effect (compose sets env before start,
        # but call-time resolution is what makes that work)
        os.environ["LDI_OLLAMA_URL"] = "http://host.docker.internal:11434"
        self.assertIn("host.docker.internal", embed_store.ollama_url())

    def test_single_source_of_truth_no_drift(self):
        # answering uses the same resolver as embed_store (one env var, no drift)
        self.assertIs(answering.ollama_url, embed_store.ollama_url)

    def test_not_named_ollama_host(self):
        # OLLAMA_HOST is Ollama's own bind var (must stay unset, D-11). Our app var
        # must be distinct so we never accidentally rebind the server.
        os.environ["LDI_OLLAMA_URL"] = "http://host.docker.internal:11434"
        self.assertEqual(embed_store.ollama_url(), "http://host.docker.internal:11434")
        self.assertIsNone(os.environ.get("OLLAMA_HOST"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
