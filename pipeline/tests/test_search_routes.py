"""Move 1c (D-69) — GET /search: retrieval-only, matter-pre-filtered, exhaustive with a
TRUE total (truncation labeled, never silent), plus BM25 mode with a version-fresh FTS
index. Temp stores only."""

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

client = TestClient(api.app)


class TestSearchRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls._cat, catalog.DEFAULT_DB = catalog.DEFAULT_DB, cls.tmp / "cat.db"
        cls._db, routes_kb.KB_DB = routes_kb.KB_DB, cls.tmp / ".lancedb_kb"
        cls._docs, routes_kb.KB_DOCS = routes_kb.KB_DOCS, cls.tmp / "kb"
        catalog.create_matter("Search Matter A")
        catalog.create_matter("Search Matter B")
        # 30 mentions of "Vantrease" in matter A across 30 docs; 1 in matter B
        for i in range(30):
            client.post(f"/kb/upload?matter=search-matter-a&filename=a{i:02d}.txt",
                        content=f"SYNTHETIC. Witness Vantrease appeared at meeting {i}.".encode())
        client.post("/kb/upload?matter=search-matter-b&filename=b.txt",
                    content=b"SYNTHETIC. Vantrease is mentioned once here in matter B.")
        deadline = time.time() + 180
        while time.time() < deadline:
            rows = client.get("/kb/documents").json()["documents"]
            if rows and all(d["status"] in ("ready", "needs_review", "failed") for d in rows):
                break
            time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        catalog.DEFAULT_DB = cls._cat
        routes_kb.KB_DB = cls._db
        routes_kb.KB_DOCS = cls._docs

    def test_mentions_is_exhaustive_with_true_total_and_pagination(self):
        r = client.get("/search?q=Vantrease&matter=search-matter-a&limit=10").json()
        self.assertEqual(r["total"], 30)          # ALL mentions counted, not top-k
        self.assertEqual(len(r["results"]), 10)
        self.assertTrue(r["truncated"])           # labeled, never silent
        r2 = client.get("/search?q=Vantrease&matter=search-matter-a&limit=10&offset=20").json()
        self.assertEqual(len(r2["results"]), 10)
        self.assertFalse(r2["truncated"])

    def test_matter_prefilter_holds(self):
        r = client.get("/search?q=Vantrease&matter=search-matter-b").json()
        self.assertEqual(r["total"], 1)
        self.assertTrue(all(x["matter"] == "search-matter-b" for x in r["results"]))

    def test_case_and_whitespace_insensitive(self):
        r = client.get("/search?q=vantrease&matter=search-matter-a&limit=5").json()
        self.assertEqual(r["total"], 30)

    def test_unknown_matter_rejected(self):
        self.assertEqual(client.get("/search?q=x&matter=nope').. DROP").status_code, 400)

    def test_empty_query_rejected(self):
        self.assertEqual(client.get("/search?q=%20&matter=search-matter-a").status_code, 400)

    def test_fts_mode_returns_ranked_results(self):
        r = client.get("/search?q=Vantrease&matter=search-matter-a&mode=fts&limit=5")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertGreaterEqual(len(body["results"]), 1)
        self.assertIsNone(body["total"])          # honest: no exact total in fts mode

    def test_fts_index_freshness_after_append(self):
        # the D-66 footgun: rows appended AFTER the index was built must still be found
        client.get("/search?q=Vantrease&matter=search-matter-a&mode=fts")  # build index
        client.post("/kb/upload?matter=search-matter-a&filename=late.txt",
                    content=b"SYNTHETIC. The zephyrquill covenant appears only here.")
        deadline = time.time() + 60
        while time.time() < deadline:
            rows = client.get("/kb/documents?matter=search-matter-a").json()["documents"]
            if all(d["status"] in ("ready", "needs_review", "failed") for d in rows):
                break
            time.sleep(0.3)
        r = client.get("/search?q=zephyrquill&matter=search-matter-a&mode=fts").json()
        self.assertGreaterEqual(len(r["results"]), 1, "stale FTS index missed appended row")


if __name__ == "__main__":
    unittest.main(verbosity=2)
