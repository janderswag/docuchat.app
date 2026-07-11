"""G-SCOPE unit layer (D1 of the adoption-tips plan, council 2026-07-11):
source_filename is a HARD pre-filter (D-18 style) — scoped retrieval returns
only that document's chunks, unknown filenames are rejected, scoping without a
matter is rejected, and default None is the byte-identical unscoped path.
Temp stores only (runs in the dev clone; the eval store is never touched)."""

import sys
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import catalog  # noqa: E402
import routes_kb  # noqa: E402
import api  # noqa: E402
import retrieval  # noqa: E402

client = TestClient(api.app)


class TestSourceFilenameScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls._cat, catalog.DEFAULT_DB = catalog.DEFAULT_DB, cls.tmp / "cat.db"
        cls._db, routes_kb.KB_DB = routes_kb.KB_DB, cls.tmp / ".lancedb_kb"
        cls._docs, routes_kb.KB_DOCS = routes_kb.KB_DOCS, cls.tmp / "kb"
        catalog.create_matter("Scope Matter")
        # indemnification lives ONLY in b.txt; a.txt..e.txt flood the matter
        for name, body in [("a.txt", "SYNTHETIC. Payment terms net thirty days. " * 30),
                           ("b.txt", "SYNTHETIC. Each party shall indemnify the other "
                                     "against third-party claims arising from breach."),
                           ("c.txt", "SYNTHETIC. Governing law is Delaware. " * 30),
                           ("d.txt", "SYNTHETIC. Termination on sixty days notice. " * 30),
                           ("e.txt", "SYNTHETIC. Confidentiality survives five years. " * 30)]:
            client.post(f"/kb/upload?matter=scope-matter&filename={name}",
                        content=body.encode())
        deadline = time.time() + 180
        while time.time() < deadline:
            rows = client.get("/kb/documents?matter=scope-matter").json()["documents"]
            if rows and all(d["status"] == "ready" for d in rows):
                break
            time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        catalog.DEFAULT_DB = cls._cat
        routes_kb.KB_DB = cls._db
        routes_kb.KB_DOCS = cls._docs

    def test_scoped_returns_only_that_documents_chunks(self):
        rows = retrieval.retrieve("indemnification obligations", matter="scope-matter",
                                  db_path=str(routes_kb.KB_DB), source_filename="b.txt")
        self.assertTrue(rows)
        self.assertTrue(all(r["source_filename"] == "b.txt" for r in rows))

    def test_scoped_hybrid_returns_only_that_documents_chunks(self):
        rows = retrieval.retrieve("indemnification obligations", matter="scope-matter",
                                  db_path=str(routes_kb.KB_DB), hybrid=True,
                                  source_filename="b.txt")
        self.assertTrue(rows)
        self.assertTrue(all(r["source_filename"] == "b.txt" for r in rows))

    def test_scope_excludes_the_globally_best_match(self):
        # filter-before-similarity, deterministically: b.txt is the best
        # semantic match for indemnification, yet a scope to a.txt must return
        # only a.txt chunks (the pre-filter runs BEFORE the similarity search)
        rows = retrieval.retrieve("indemnification obligations", matter="scope-matter",
                                  db_path=str(routes_kb.KB_DB), source_filename="a.txt")
        self.assertTrue(rows)
        self.assertTrue(all(r["source_filename"] == "a.txt" for r in rows))

    def test_apostrophe_filename_round_trips(self):
        # a legitimately quoted filename must be scopeable (escaped), not just
        # safely rejected — pins the chr(39)-doubling against upgrades
        client.post("/kb/upload?matter=scope-matter&filename=o'brien.txt",
                    content=b"SYNTHETIC. Deposition of witness O'Brien, page one.")
        deadline = time.time() + 60
        while time.time() < deadline:
            rows = client.get("/kb/documents?matter=scope-matter").json()["documents"]
            if rows and all(d["status"] == "ready" for d in rows):
                break
            time.sleep(0.3)
        rows = retrieval.retrieve("deposition witness", matter="scope-matter",
                                  db_path=str(routes_kb.KB_DB),
                                  source_filename="o'brien.txt")
        self.assertTrue(rows)
        self.assertTrue(all(r["source_filename"] == "o'brien.txt" for r in rows))

    def test_unknown_filename_rejected(self):
        with self.assertRaises(ValueError):
            retrieval.retrieve("anything", matter="scope-matter",
                               db_path=str(routes_kb.KB_DB),
                               source_filename="nope.txt")

    def test_filename_known_only_in_another_matter_rejected(self):
        # validation is PER MATTER: a real filename from a different matter must
        # not silently scope (that would be a cross-matter information channel)
        catalog.create_matter("Other Matter")
        client.post("/kb/upload?matter=other-matter&filename=z.txt",
                    content=b"SYNTHETIC. Other matter content.")
        deadline = time.time() + 60
        while time.time() < deadline:
            rows = client.get("/kb/documents?matter=other-matter").json()["documents"]
            if rows and all(d["status"] == "ready" for d in rows):
                break
            time.sleep(0.3)
        with self.assertRaises(ValueError):
            retrieval.retrieve("anything", matter="scope-matter",
                               db_path=str(routes_kb.KB_DB), source_filename="z.txt")

    def test_scope_requires_matter(self):
        with self.assertRaises(ValueError):
            retrieval.retrieve("anything", matter=None,
                               db_path=str(routes_kb.KB_DB),
                               source_filename="b.txt")

    def test_default_none_is_unscoped(self):
        a = retrieval.retrieve("indemnification", matter="scope-matter",
                               db_path=str(routes_kb.KB_DB))
        b = retrieval.retrieve("indemnification", matter="scope-matter",
                               db_path=str(routes_kb.KB_DB), source_filename=None)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
