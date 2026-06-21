"""T-CLAUSE API proof: the loopback Contract Review route over extract_clauses.

GET /clauses/taxonomy serves the curated checklist. POST /clauses/review {matter, doc_id?}
runs the checklist for a matter (validated against the catalog allowlist, D-35) and returns
the structured result, enriching each verified citation with its catalog doc_id so the UI
can request the existing page-thumbnail + cited-span highlight. The route is read-only: no
action verbs (PUT/PATCH/DELETE -> 405). extract_clauses is monkeypatched here so the HTTP
contract is exercised fast + deterministically; the real LLM path is proven in
test_clauses.TestIntegrationAgainstBaseline.
"""

import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import catalog  # noqa: E402
import routes_clauses  # noqa: E402
import api  # noqa: E402

client = TestClient(api.app)


class TestTaxonomyEndpoint(unittest.TestCase):
    def test_serves_the_curated_checklist(self):
        r = client.get("/clauses/taxonomy")
        self.assertEqual(r.status_code, 200)
        clauses = r.json()["clauses"]
        ids = {c["id"] for c in clauses}
        self.assertIn("indemnification", ids)
        self.assertIn("governing_law", ids)
        for c in clauses:
            self.assertTrue(c["question"].strip())


class TestReviewEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls._cat, catalog.DEFAULT_DB = catalog.DEFAULT_DB, cls.tmp / "cat.db"
        catalog.create_matter("Demo Matter")
        p = cls.tmp / "demo_msa.pdf"
        p.write_bytes(b"%PDF-1.4 synthetic")
        cls.doc = catalog.add_document("demo-matter", p, status="ready")

    @classmethod
    def tearDownClass(cls):
        catalog.DEFAULT_DB = cls._cat

    def setUp(self):
        self._orig = routes_clauses.extract_clauses

    def tearDown(self):
        routes_clauses.extract_clauses = self._orig

    def _fake(self, **canned):
        def fake_extract(matter, doc_id=None, db_path=None, catalog_db=None, **kw):
            self.assertEqual(matter, "demo-matter")
            return canned
        routes_clauses.extract_clauses = fake_extract

    def test_review_enriches_found_citation_with_doc_id(self):
        self._fake(matter="demo-matter", doc_id=None, summary={"found": 1,
                   "potentially_missing": 0, "not_confirmed": 0, "total": 1},
                   results=[{"id": "indemnification", "name": "Indemnification",
                             "category": "Risk Allocation", "question": "?",
                             "doc_types": ["contract"], "status": "found",
                             "value": "Each party shall indemnify...",
                             "citations": [{"filename": "demo_msa.pdf", "page": 3,
                                            "chunk_id": "C1", "span": "shall indemnify",
                                            "char_start": 1, "char_end": 9}],
                             "rejected_claims": []}])
        r = client.post("/clauses/review", json={"matter": "demo-matter"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["summary"]["found"], 1)
        cite = body["results"][0]["citations"][0]
        self.assertEqual(cite["doc_id"], self.doc["id"])  # enriched for the highlight URL

    def test_missing_clause_keeps_zero_citations(self):
        self._fake(matter="demo-matter", doc_id=None, summary={"found": 0,
                   "potentially_missing": 1, "not_confirmed": 0, "total": 1},
                   results=[{"id": "arbitration", "name": "Arbitration",
                             "category": "Dispute Resolution", "question": "?",
                             "doc_types": ["contract"], "status": "potentially_missing",
                             "value": "Not located in the documents.",
                             "citations": [], "rejected_claims": []}])
        r = client.post("/clauses/review", json={"matter": "demo-matter"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["results"][0]["citations"], [])

    def test_unknown_matter_is_400(self):
        r = client.post("/clauses/review", json={"matter": "no-such-matter"})
        self.assertEqual(r.status_code, 400)

    def test_no_action_verbs(self):
        for verb in ("put", "patch", "delete"):
            r = getattr(client, verb)("/clauses/review")
            self.assertEqual(r.status_code, 405, f"{verb.upper()} should be 405")


if __name__ == "__main__":
    unittest.main(verbosity=2)
