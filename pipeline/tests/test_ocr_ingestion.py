"""G-SC2 proof: per-page OCR routing for image-only/scanned PDFs (D-15, CE_PLAN §8,
SC-2). Born-digital pages stay on the fast PyMuPDF path with output UNCHANGED; image-
only pages route through local Tesseract; OCR text lands on its correct page_number and
reassembles in order; empty/low-confidence OCR is FLAGGED (fail-loud), not indexed as
authoritative; OCR runs fully local (zero network sockets).
"""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

import fitz

PIPELINE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PIPELINE_DIR.parent
PDF_DIR = REPO_ROOT / "documents" / "synthetic_corpus" / "pdf"
MANIFEST = REPO_ROOT / "eval" / "golden_manifest.jsonl"

sys.path.insert(0, str(PIPELINE_DIR))
from ingestion import extract_pages, extract_pages_ocr, _ocr_verdict  # noqa: E402
from build_scanned_corpus import rasterize_to_image_pdf  # noqa: E402

DOC = "greenfield_castellano_lease.pdf"  # 12 present facts, 3 pages
# A premises address unique to page 1 — good for the page-boundary test.
UNIQUE_P1_SPAN = "1147 Aldergrove Avenue, Unit 3B, Crestwood, OH 44122"

# OCR is slow; rasterize + OCR the shared doc ONCE for the whole module.
_SHARED = {}


def setUpModule():
    tmp = tempfile.mkdtemp()
    scanned = Path(tmp) / DOC
    rasterize_to_image_pdf(PDF_DIR / DOC, scanned, dpi=300)
    _SHARED["scanned"] = scanned
    _SHARED["pages"] = extract_pages_ocr(scanned)


def _norm(t):
    t = re.sub(r"-\n", "-", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def _coverage(haystack, span):
    """Fraction of the span's word tokens present in haystack (OCR isn't byte-perfect,
    so we score normalized token coverage, not an exact substring)."""
    ptoks = set(_norm(haystack).split())
    stoks = _norm(span).split()
    if not stoks:
        return 0.0
    return sum(1 for w in stoks if w in ptoks) / len(stoks)


def _present_spans(filename):
    out = []
    with open(MANIFEST, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r["filename"] == filename and not r["expected_absent_topics"]:
                out.append(r)
    return out


class TestOcrRecoversKnownText(unittest.TestCase):
    def test_image_only_pages_route_to_tesseract_and_recover_5_spans(self):
        pages = _SHARED["pages"]
        # every page of the image-only PDF routed through OCR (no text layer)
        self.assertTrue(pages and all(p["source"] == "tesseract" for p in pages))
        alltext = "\n".join(p["page_text"] for p in pages)
        spans = _present_spans(DOC)
        recovered = [s for s in spans if _coverage(alltext, s["verbatim_span"]) >= 0.85]
        self.assertGreaterEqual(
            len(recovered), 5,
            f"only {len(recovered)}/{len(spans)} known spans recovered via OCR",
        )


class TestOcrPageBoundaryIntegrity(unittest.TestCase):
    def test_known_fact_ocrs_onto_its_manifest_page_not_another(self):
        by_page = {p["page_number"]: p["page_text"] for p in _SHARED["pages"]}
        self.assertIn(1, by_page)
        # the unique page-1 span recovers on page 1 ...
        self.assertGreaterEqual(_coverage(by_page[1], UNIQUE_P1_SPAN), 0.85)
        # ... and is NOT present on any other page (page boundaries preserved)
        for pg, text in by_page.items():
            if pg != 1:
                self.assertLess(_coverage(text, UNIQUE_P1_SPAN), 0.5,
                                f"page-1 span leaked onto page {pg}")

    def test_multiple_facts_land_on_their_own_pages(self):
        by_page = {p["page_number"]: p["page_text"] for p in _SHARED["pages"]}
        on_own_page = 0
        for s in _present_spans(DOC):
            pg = s["page_number"]
            if pg in by_page and _coverage(by_page[pg], s["verbatim_span"]) >= 0.85:
                on_own_page += 1
        self.assertGreaterEqual(on_own_page, 3)


class TestBornDigitalUnchanged(unittest.TestCase):
    def test_born_digital_pdf_routes_pymupdf_with_identical_text(self):
        src = PDF_DIR / DOC
        base = extract_pages(src)
        routed = extract_pages_ocr(src)
        self.assertEqual(len(base), len(routed))
        for b, r in zip(base, routed):
            self.assertEqual(r["source"], "pymupdf")  # OCR NOT applied
            self.assertFalse(r["ocr_failed"])
            self.assertEqual(r["page_text"], b["page_text"])  # byte-identical fast path
            self.assertEqual(r["page_number"], b["page_number"])
            self.assertEqual(r["source_filename"], b["source_filename"])


class TestFailLoudVerdict(unittest.TestCase):
    def test_empty_text_is_flagged(self):
        failed, reason = _ocr_verdict("", 95.0, min_confidence=50)
        self.assertTrue(failed)
        self.assertIn("empty", reason.lower())

    def test_low_confidence_is_flagged(self):
        failed, reason = _ocr_verdict("garbled qx zte", 12.0, min_confidence=50)
        self.assertTrue(failed)
        self.assertIn("confidence", reason.lower())

    def test_good_text_is_not_flagged(self):
        failed, reason = _ocr_verdict("clean recovered legal text", 88.0, min_confidence=50)
        self.assertFalse(failed)
        self.assertIsNone(reason)


class TestFailLoudBlankPage(unittest.TestCase):
    def test_blank_image_page_is_flagged_not_authoritative(self):
        tmp = Path(tempfile.mkdtemp()) / "blank.pdf"
        with fitz.open() as doc:
            page = doc.new_page(width=612, height=792)
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 1000, 1294))
            pix.clear_with(255)  # blank white
            page.insert_image(fitz.Rect(0, 0, 612, 792), stream=pix.tobytes("png"))
            doc.save(tmp)
        pages = extract_pages_ocr(tmp)
        self.assertEqual(len(pages), 1)
        self.assertTrue(pages[0]["ocr_failed"])
        self.assertTrue(pages[0]["flag_reason"])
        self.assertEqual(pages[0]["page_text"].strip(), "")  # no authoritative garbage


class TestNoEgressDuringOcr(unittest.TestCase):
    def test_ocr_extraction_makes_no_outbound_connection(self):
        import socket
        scanned = Path(tempfile.mkdtemp()) / DOC
        rasterize_to_image_pdf(PDF_DIR / DOC, scanned, dpi=200)
        original = socket.socket.connect

        def blocked(self, *a, **k):
            raise AssertionError(f"unexpected network egress to {a!r}")

        socket.socket.connect = blocked
        try:
            pages = extract_pages_ocr(scanned)
            self.assertTrue(pages and all(p["source"] == "tesseract" for p in pages))
        finally:
            socket.socket.connect = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
