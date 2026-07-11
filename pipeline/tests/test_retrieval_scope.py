"""G-SCOPE unit layer (D1 of the adoption-tips plan, council 2026-07-11):
source_filename is a HARD pre-filter (D-18 style) — scoped retrieval returns
only that document's chunks, unknown filenames are rejected, scoping without a
matter is rejected, and default None is the byte-identical unscoped path.
Temp stores only (runs in the dev clone; the eval store is never touched)."""

import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import catalog  # noqa: E402
import routes_kb  # noqa: E402
import api  # noqa: E402
import answering  # noqa: E402
import retrieval  # noqa: E402

client = TestClient(api.app)


def _ollama_up():
    try:
        with urllib.request.urlopen(f"{answering.ollama_url()}/api/tags",
                                    timeout=3):
            return True
    except Exception:
        return False


_SAVED = {}


def setUpModule():
    """One temp store for the whole module (the live class below needs the same
    fixture AFTER the unit class finishes — per-class teardown would yank it)."""
    tmp = Path(tempfile.mkdtemp())
    _SAVED["cat"], catalog.DEFAULT_DB = catalog.DEFAULT_DB, tmp / "cat.db"
    _SAVED["db"], routes_kb.KB_DB = routes_kb.KB_DB, tmp / ".lancedb_kb"
    _SAVED["docs"], routes_kb.KB_DOCS = routes_kb.KB_DOCS, tmp / "kb"
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


def tearDownModule():
    catalog.DEFAULT_DB = _SAVED["cat"]
    routes_kb.KB_DB = _SAVED["db"]
    routes_kb.KB_DOCS = _SAVED["docs"]


class TestSourceFilenameScope(unittest.TestCase):
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


class TestAnswerScopeThreading(unittest.TestCase):
    """D2: answer() threads source_filename into BOTH retrieval passes (the base
    pass and the refusal-triggered second pass) — a scoped ask that refuses must
    not widen back out to the whole matter. Mocked; no Ollama needed."""

    FAKE_CHUNK = {"chunk_id": "C1", "source_filename": "b.txt", "page_number": 1,
                  "char_start": 0, "char_end": 10, "text": "SYNTHETIC.",
                  "section": "s"}

    def test_both_passes_receive_the_scope(self):
        calls = []

        def fake_retrieve(question, **kw):
            calls.append(kw)
            return [dict(self.FAKE_CHUNK)]

        with mock.patch.object(answering, "retrieve", fake_retrieve), \
             mock.patch.object(answering, "_chat",
                               return_value=answering.REFUSAL):
            answering.answer("indemnification?", matter="m",
                             db_path="/tmp/x", source_filename="b.txt")
        self.assertEqual(len(calls), 2)   # base pass + refusal second pass
        for kw in calls:
            self.assertEqual(kw.get("source_filename"), "b.txt")

    def test_default_path_passes_no_scope(self):
        calls = []

        def fake_retrieve(question, **kw):
            calls.append(kw)
            return [dict(self.FAKE_CHUNK)]

        with mock.patch.object(answering, "retrieve", fake_retrieve), \
             mock.patch.object(answering, "_chat", return_value="An answer."):
            answering.answer("anything?", matter="m", db_path="/tmp/x")
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0].get("source_filename"))

    def test_answer_stream_threads_the_scope_through_both_passes(self):
        calls = []

        def fake_retrieve(question, **kw):
            calls.append(kw)
            return [dict(self.FAKE_CHUNK)]

        # first stream refuses -> the streaming second pass must stay scoped
        with mock.patch.object(answering, "retrieve", fake_retrieve), \
             mock.patch.object(answering, "_stream_tokens",
                               side_effect=[iter([answering.REFUSAL]),
                                            iter(["Still nothing."])]):
            list(answering.answer_stream("q?", matter="m", db_path="/tmp/x",
                                         source_filename="b.txt"))
        self.assertEqual(len(calls), 2)   # base + streaming second pass
        for kw in calls:
            self.assertEqual(kw.get("source_filename"), "b.txt")


@unittest.skipUnless(_ollama_up(), "loopback Ollama not running")
class TestScopedAnswerLive(unittest.TestCase):
    """D2 integration (live loopback Ollama, temp store): a scoped answer about
    indemnification against the flooded matter cites only b.txt or refuses."""

    def test_scoped_answer_cites_only_the_scoped_document(self):
        res = answering.answer(
            "What are each party's indemnification obligations?",
            matter="scope-matter", db_path=str(routes_kb.KB_DB),
            source_filename="b.txt")
        if answering._is_refusal(res["answer_text"]):
            self.assertEqual(res["citations"], [])   # honest refusal, no cite
        else:
            self.assertTrue(res["citations"])
            for c in res["citations"]:
                self.assertEqual(c["filename"], "b.txt")


EVAL_DB = PIPELINE_DIR / ".lancedb"
PEMBERTON = "Pemberton Logistics (Nimbus MSA)"


def _eval_store_ready():
    """The dev clone carries an EMPTY .lancedb dir (no chunks table) — probe
    the table, not just the path, so the class skips honestly there."""
    if not EVAL_DB.exists():
        return False
    try:
        import lancedb
        lancedb.connect(str(EVAL_DB)).open_table("chunks")
        return True
    except Exception:
        return False


@unittest.skipUnless(_eval_store_ready() and _ollama_up(),
                     "eval .lancedb baseline (chunks) + loopback Ollama required")
class TestScopeAgainstEvalBaseline(unittest.TestCase):
    """D6 G-SCOPE live proof (read-only against the eval baseline, D-31): the
    Pemberton matter holds the MSA (indemnification on page 3, golden F-009)
    plus the Renfrew demand letter (no indemnification clause). A scoped ask
    finds the clause in the document that has it and refuses in the one that
    does not — the exact false-'missing' scenario the engine cycle fixes."""

    QUESTION = ("What are each party's indemnification obligations under this "
                "agreement: who must defend, indemnify, or hold harmless whom?")

    def test_scoped_to_the_msa_finds_it(self):
        res = answering.answer(self.QUESTION, matter=PEMBERTON,
                               db_path=str(EVAL_DB),
                               source_filename="nimbus_pemberton_msa.pdf")
        self.assertFalse(answering._is_refusal(res["answer_text"]),
                         res["answer_text"])
        self.assertTrue(res["citations"], "found without a verified citation")
        for c in res["citations"]:
            self.assertEqual(c["filename"], "nimbus_pemberton_msa.pdf")

    def test_scoped_to_the_demand_letter_refuses(self):
        res = answering.answer(self.QUESTION, matter=PEMBERTON,
                               db_path=str(EVAL_DB),
                               source_filename="renfrew_demand_letter.pdf")
        # never a fabricated citation: either an honest refusal, or (if prose
        # slipped through) zero span-verified citations on the wrong document
        if not answering._is_refusal(res["answer_text"]):
            self.assertEqual(
                [c for c in res["citations"]
                 if c["filename"] != "renfrew_demand_letter.pdf"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
