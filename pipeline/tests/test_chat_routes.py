"""Task 4 proof: matter-scoped cited chat over .lancedb_kb + persisted threads/history.

A seeded matter answers with a chunk-derived, span-verified citation and persists a
thread; an EMPTY matter returns the exact D-30 refusal with no citation; chat for
matter X never returns a chunk from matter Y (D-18 scoping). Temp KB only."""

import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import catalog  # noqa: E402
import routes_kb  # noqa: E402
import kb_ingest  # noqa: E402
import api  # noqa: E402
from answering import REFUSAL  # noqa: E402

client = TestClient(api.app)


class TestChatRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls._cat, catalog.DEFAULT_DB = catalog.DEFAULT_DB, cls.tmp / "cat.db"
        cls._db, routes_kb.KB_DB = routes_kb.KB_DB, cls.tmp / ".lancedb_kb"
        for name in ("Alpha Matter", "Beta Matter", "Empty Matter"):
            catalog.create_matter(name)
        # seed Alpha + Beta with distinct, uniquely-keyed synthetic facts
        cls._seed("alpha-matter", "alpha_fee.txt", "SYNTHETIC. The alpha consulting fee is $1,234 monthly.")
        cls._seed("beta-matter", "beta_code.txt", "SYNTHETIC. The beta access code is ZZ-999 exactly.")

    @classmethod
    def _seed(cls, slug, name, text):
        p = cls.tmp / name
        p.write_text(text, encoding="utf-8")
        d = catalog.add_document(slug, p)
        kb_ingest.ingest_document(d["id"], p, slug, db_path=routes_kb.KB_DB, catalog_db=catalog.DEFAULT_DB)

    @classmethod
    def tearDownClass(cls):
        catalog.DEFAULT_DB = cls._cat
        routes_kb.KB_DB = cls._db

    def test_seeded_matter_answers_with_citation_and_persists_thread(self):
        r = client.post("/chat", json={"question": "What is the alpha consulting fee?",
                                       "matter": "alpha-matter"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["rejected_claims"], [])
        self.assertTrue(body["citations"], f"no citation: {body['answer_text']!r}")
        self.assertEqual(body["citations"][0]["filename"], "alpha_fee.txt")
        self.assertIn("1,234", body["answer_text"])
        self.assertIsNotNone(body["thread_id"])
        # persisted in history
        threads = client.get("/chat/threads").json()["threads"]
        self.assertTrue(any(t["id"] == body["thread_id"] for t in threads))
        msgs = client.get("/chat/threads/" + str(body["thread_id"])).json()["messages"]
        self.assertGreaterEqual(len(msgs), 2)  # user + assistant

    def test_empty_matter_returns_d30_refusal_no_citation(self):
        r = client.post("/chat", json={"question": "What is anything?", "matter": "empty-matter"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn(REFUSAL, body["answer_text"])
        self.assertEqual(body["citations"], [])

    def test_chat_is_matter_scoped_no_cross_matter_citation(self):
        # ask Beta's unique fact while scoped to Alpha -> must NOT cite the beta doc
        r = client.post("/chat", json={"question": "What is the beta access code ZZ-999?",
                                       "matter": "alpha-matter"})
        body = r.json()
        for c in body["citations"]:
            self.assertNotEqual(c["filename"], "beta_code.txt", "cross-matter leak")


if __name__ == "__main__":
    unittest.main(verbosity=2)
