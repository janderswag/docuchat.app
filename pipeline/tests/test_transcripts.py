"""Move 2a/2b/2c (D-70) — transcript engine tests, on a synthetic gutter-numbered
deposition with facts planted at KNOWN page:line positions.

The trust rule under test everywhere: page:line is DERIVED from verifier-confirmed span
offsets through the stored line map — never model-asserted; ambiguous spans (same text
twice on a page) yield NO line range (precise or absent); condensed 4-up sheets FAIL
LOUD; prose documents are untouched. E2E (live local LLM) proves a chat answer carries
a correct page:line citation."""

import sys
import tempfile
import time
import unittest
from pathlib import Path

import fitz

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import catalog  # noqa: E402
import routes_kb  # noqa: E402
import transcript_extract as te  # noqa: E402

# ---------------------------------------------------------------------------------
# Fixture: an 8-page synthetic deposition, 20 numbered lines per page. Known facts:
#   page 4, lines 12-14: the $3,415/month Vexcorp compressor maintenance fee
#   page 6: two IDENTICAL "A. Yes." answers (lines 8 and 16) -> ambiguity trap
DEPO_LINES = {}
for p in range(1, 9):
    DEPO_LINES[p] = [f"Q. Routine scheduling question number {p}-{l}."
                     if l % 2 else f"A. Routine answer text {p}-{l}."
                     for l in range(1, 21)]
DEPO_LINES[1][0] = "SYNTHETIC DEPOSITION OF MARCUS VELLUM - NOT REAL"
DEPO_LINES[1][1] = "BY MR. OKONKWO:"
DEPO_LINES[4][11] = "Q. What was the monthly maintenance fee for the"
DEPO_LINES[4][12] = "compressor unit at the Toledo facility?"
DEPO_LINES[4][13] = "A. It was $3,415 per month, paid to Vexcorp."
DEPO_LINES[6][7] = "A. Yes."
DEPO_LINES[6][15] = "A. Yes."


def make_depo_pdf(path):
    with fitz.open() as doc:
        for p in range(1, 9):
            page = doc.new_page(width=612, height=792)
            y = 72
            for i, line in enumerate(DEPO_LINES[p], 1):
                page.insert_text((50, y), f"{i:>2}", fontsize=10, fontname="cour")
                page.insert_text((90, y), line, fontsize=10, fontname="cour")
                y += 26
            doc.save(str(path)) if p == 8 else None
    return path


def make_depo_txt(path):
    out = []
    for p in range(1, 9):
        out.append(f"Page {p}")
        for i, line in enumerate(DEPO_LINES[p], 1):
            out.append(f"{i:>2}  {line}")
    path.write_text("\n".join(out), encoding="utf-8")
    return path


def make_condensed_pdf(path):
    """A 4-up condensed sheet: 80 numbered lines with restarts on one PDF page."""
    with fitz.open() as doc:
        page = doc.new_page(width=612, height=792)
        y = 30
        for rep in range(4):
            for i in range(1, 21):
                page.insert_text((40 + 0 * rep, y), f"{i:>2}  condensed line", fontsize=5)
                y += 9
        doc.save(str(path))
    return path


class TestExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.pdf = make_depo_pdf(cls.tmp / "depo.pdf")
        cls.txt = make_depo_txt(cls.tmp / "depo.txt")

    def test_pdf_gutter_stripped_and_line_map_faithful(self):
        pages = te.extract_transcript_pdf(self.pdf)
        self.assertEqual(len(pages), 8)
        pno, clean, entries = pages[3]           # page 4
        self.assertEqual(pno, 4)
        self.assertEqual(len(entries), 20)
        for ln, s, e in entries:                 # offset invariant vs CLEAN text
            self.assertEqual(clean[s:e], DEPO_LINES[4][ln - 1])
        self.assertNotRegex(clean.splitlines()[0], r"^\s*\d")  # no gutter residue

    def test_txt_pages_and_lines(self):
        pages = te.extract_transcript_txt(self.txt)
        self.assertEqual([p for p, _, _ in pages], list(range(1, 9)))
        _, clean, entries = pages[5]             # page 6
        self.assertEqual(len(entries), 20)
        ln8 = next((s, e) for ln, s, e in entries if ln == 8)
        self.assertEqual(clean[ln8[0]:ln8[1]], "A. Yes.")

    def test_condensed_sheet_fails_loud(self):
        condensed = make_condensed_pdf(self.tmp / "condensed.pdf")
        with self.assertRaises(te.CondensedTranscriptError):
            te.extract_transcript_pdf(condensed)

    def test_chunks_one_per_page_with_speakers_in_embedding_only(self):
        pages = te.extract_transcript_pdf(self.pdf)
        chunks = te.chunk_transcript_pages(pages, "m-depo", "depo.pdf")
        self.assertEqual(len(chunks), 8)
        c4 = chunks[3]
        self.assertEqual(c4["document_type"], "transcript")
        self.assertEqual(c4["char_start"], 0)
        self.assertEqual(c4["text"][c4["char_start"]:c4["char_end"]], c4["text"])
        self.assertIn("Speakers:", c4["embedding_text"])
        self.assertNotIn("Speakers:", c4["text"])         # metadata never citable text
        # cross-page context rides in embedding_text only
        self.assertIn("previous page ends", chunks[1]["embedding_text"])
        self.assertNotIn("previous page ends", chunks[1]["text"])


class TestDeriveLines(unittest.TestCase):
    def setUp(self):
        pages = te.extract_transcript_pdf(make_depo_pdf(Path(tempfile.mkdtemp()) / "d.pdf"))
        self.p4 = pages[3]
        self.p6 = pages[5]

    def test_known_span_maps_to_correct_lines(self):
        _, clean, entries = self.p4
        span = "It was $3,415 per month, paid to Vexcorp."
        s = clean.find(span)
        self.assertGreater(s, -1)
        lines = te.derive_lines(entries, s, s + len(span), clean, span)
        self.assertEqual(lines, "14")

    def test_multiline_span_maps_to_range(self):
        _, clean, entries = self.p4
        span = ("Q. What was the monthly maintenance fee for the\n"
                "compressor unit at the Toledo facility?")
        s = clean.find("Q. What was the monthly maintenance fee")
        lines = te.derive_lines(entries, s, s + len(span), clean, span)
        self.assertEqual(lines, "12-13")

    def test_ambiguous_span_yields_no_lines(self):
        _, clean, entries = self.p6
        span = "A. Yes."
        s = clean.find(span)
        self.assertIsNone(te.derive_lines(entries, s, s + len(span), clean, span),
                          "ambiguous span must fall back to page-only citation")

    def test_empty_map_yields_none(self):
        self.assertIsNone(te.derive_lines([], 0, 10, "text", "text"))


class TestTranscriptIngestAndE2E(unittest.TestCase):
    """Live path: upload -> worker ingest -> line map saved -> /chat answer carries a
    DERIVED page:line citation. Uses the real local Ollama like the other e2e suites."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import api
        cls.client = TestClient(api.app)
        cls.tmp = Path(tempfile.mkdtemp())
        cls._cat, catalog.DEFAULT_DB = catalog.DEFAULT_DB, cls.tmp / "cat.db"
        cls._db, routes_kb.KB_DB = routes_kb.KB_DB, cls.tmp / ".lancedb_kb"
        cls._docs, routes_kb.KB_DOCS = routes_kb.KB_DOCS, cls.tmp / "kb"
        catalog.create_matter("Depo Matter")
        pdf = make_depo_pdf(cls.tmp / "vellum_depo.pdf")
        r = cls.client.post(
            "/kb/upload?matter=depo-matter&filename=vellum_depo.pdf&doc_type=transcript",
            content=pdf.read_bytes())
        assert r.status_code == 200, r.text
        cls.doc = r.json()
        deadline = time.time() + 240
        while time.time() < deadline:
            row = catalog.get_document(cls.doc["id"])
            if row and row["status"] in ("ready", "needs_review", "failed"):
                break
            time.sleep(0.3)
        cls.final_status = row["status"]

    @classmethod
    def tearDownClass(cls):
        catalog.DEFAULT_DB = cls._cat
        routes_kb.KB_DB = cls._db
        routes_kb.KB_DOCS = cls._docs

    def test_ingest_ready_with_line_map(self):
        self.assertEqual(self.final_status, "ready")
        entries = catalog.line_map_for_page(self.doc["id"], 4)
        self.assertEqual(len(entries), 20)

    def test_condensed_upload_fails_with_clear_reason(self):
        condensed = make_condensed_pdf(self.tmp / "condensed.pdf")
        r = self.client.post(
            "/kb/upload?matter=depo-matter&filename=condensed.pdf&doc_type=transcript",
            content=condensed.read_bytes())
        doc = r.json()
        deadline = time.time() + 120
        while time.time() < deadline:
            row = catalog.get_document(doc["id"])
            if row["status"] in ("ready", "needs_review", "failed"):
                break
            time.sleep(0.3)
        self.assertEqual(row["status"], "failed")
        self.assertIn("condensed", row["reason"])

    def test_chat_answer_carries_derived_page_line(self):
        r = self.client.post("/chat", json={
            "question": "What was the monthly maintenance fee for the compressor unit?",
            "matter": "depo-matter"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["citations"], f"no citation: {body['answer_text']!r}")
        c = body["citations"][0]
        self.assertEqual(c["filename"], "vellum_depo.pdf")
        self.assertEqual(int(c["page"]), 4)
        self.assertIn("3,415", body["answer_text"])
        self.assertIn("lines", c, "transcript citation missing derived page:line")
        lo = int(str(c["lines"]).split("-")[0])
        self.assertTrue(12 <= lo <= 14, f"derived lines {c['lines']} outside the fact")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDigest(unittest.TestCase):
    """Move 2d: the digest walks ALL pages, keeps only verifier-confirmed bullets, and
    exports a Word table. Reuses the live ingest from TestTranscriptIngestAndE2E's
    class fixtures via its own upload (isolated stores)."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import api
        cls.client = TestClient(api.app)
        cls.tmp = Path(tempfile.mkdtemp())
        cls._cat, catalog.DEFAULT_DB = catalog.DEFAULT_DB, cls.tmp / "cat.db"
        cls._db, routes_kb.KB_DB = routes_kb.KB_DB, cls.tmp / ".lancedb_kb"
        cls._docs, routes_kb.KB_DOCS = routes_kb.KB_DOCS, cls.tmp / "kb"
        catalog.create_matter("Digest Matter")
        pdf = make_depo_pdf(cls.tmp / "digest_depo.pdf")
        r = cls.client.post(
            "/kb/upload?matter=digest-matter&filename=digest_depo.pdf&doc_type=transcript",
            content=pdf.read_bytes())
        cls.doc = r.json()
        deadline = time.time() + 240
        while time.time() < deadline:
            row = catalog.get_document(cls.doc["id"])
            if row and row["status"] in ("ready", "needs_review", "failed"):
                break
            time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        catalog.DEFAULT_DB = cls._cat
        routes_kb.KB_DB = cls._db
        routes_kb.KB_DOCS = cls._docs

    def _parse_sse(self, text):
        events = []
        for blk in text.split("\n\n"):
            name, data = None, None
            for line in blk.splitlines():
                if line.startswith("event:"):
                    name = line[6:].strip()
                elif line.startswith("data:"):
                    import json as _json
                    data = _json.loads(line[5:].strip())
            if name:
                events.append((name, data))
        return events

    def test_digest_covers_all_pages_and_only_verified_bullets(self):
        r = self.client.post(f"/transcripts/{self.doc['id']}/digest")
        self.assertEqual(r.status_code, 200, r.text)
        events = self._parse_sse(r.text)
        kinds = [k for k, _ in events]
        self.assertIn("meta", kinds)
        self.assertIn("done", kinds)
        meta = dict(events)[
            "meta"] if "meta" in dict(events) else None
        done = [d for k, d in events if k == "done"][0]
        self.assertEqual(done["stats"]["pages"], 8)          # ALL pages, not top-k
        self.assertIn("all 8", done["coverage"])
        bullets = [b for t in done["topics"] for b in t["bullets"]]
        self.assertTrue(bullets, "digest produced no verified bullets")
        # the planted fact must be in the digest, with derived page:line
        fact = [b for b in bullets if "3,415" in (b["span"] + b["text"])]
        self.assertTrue(fact, f"planted fact missing from digest: {bullets}")
        self.assertEqual(int(fact[0]["page"]), 4)
        self.assertTrue(fact[0].get("lines"), "planted-fact bullet lacks page:line")
        self.__class__.digest_payload = done

    def test_docx_export_renders(self):
        payload = getattr(self.__class__, "digest_payload", None)
        if payload is None:
            self.skipTest("digest test did not run first")
        r = self.client.post("/transcripts/digest.docx", json=payload)
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.content), 5000)
        from docx import Document
        import io as _io
        doc = Document(_io.BytesIO(r.content))
        cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
        self.assertTrue(any("3,415" in c for c in cells), "fact missing from Word table")
        self.assertTrue(any("p.4" in c for c in cells), "cite missing from Word table")

    def test_digest_404_for_non_transcript(self):
        self.assertEqual(self.client.post("/transcripts/99999/digest").status_code, 404)
