"""M2-6 proof: mechanical span-level citation verification (D-19).

Deterministic checks (no LLM) on the verifier: a true span verifies with
chunk-derived filename+page and page offsets that bound it; a span differing only
by PDF reflow whitespace/hyphenation still verifies (no false reject); a fabricated
span and a mis-paged (wrong-chunk) citation are rejected and surfaced; the refusal
path yields no claims. Plus a few real present facts answered end-to-end, and a
loopback-only egress check.
"""

import json
import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PIPELINE_DIR.parent
MANIFEST = REPO_ROOT / "eval" / "golden_manifest.jsonl"
QUESTIONS = REPO_ROOT / "eval" / "golden_questions.jsonl"

sys.path.insert(0, str(PIPELINE_DIR))
from verifier import verify_answer, locate_span  # noqa: E402
from answering import answer, REFUSAL  # noqa: E402

PEMBERTON = "Pemberton Logistics (Nimbus MSA)"

# A synthetic grounding chunk whose text is a page slice [40, 200) (char_start=40),
# with a PDF line-wrap newline and a hyphenated compound wrapped across a line.
_CHUNK = {
    "chunk_id": "C1", "source_filename": "nimbus_pemberton_msa.pdf", "page_number": 1,
    "char_start": 40, "char_end": 200,
    "text": "This Agreement is effective as of March 14, 2024 and renews for twenty-\nfour (24) months.",
}


def _read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _fact(fid):
    return next(r for r in _read_jsonl(MANIFEST) if r["fact_id"] == fid)


def _q(fid):
    return next(r["question"] for r in _read_jsonl(QUESTIONS) if r["fact_id"] == fid)


class TestTruePositive(unittest.TestCase):
    def test_real_span_verifies_with_chunk_derived_page_and_bounding_offsets(self):
        ans = ('The effective date is March 14, 2024 [document: X.pdf, page: 99, chunk: C1, '
               'span: "effective as of March 14, 2024"].')
        out = verify_answer(ans, [_CHUNK])
        self.assertEqual(out["rejected_claims"], [])
        self.assertEqual(len(out["citations"]), 1)
        c = out["citations"][0]
        self.assertEqual(c["page"], 1)  # chunk-derived, not 99
        self.assertEqual(c["filename"], "nimbus_pemberton_msa.pdf")
        # offsets are page-absolute and land within the chunk's [char_start, char_end]
        self.assertGreaterEqual(c["char_start"], _CHUNK["char_start"])
        self.assertLessEqual(c["char_end"], _CHUNK["char_end"])
        # and the raw page slice at those offsets really is the span
        local = _CHUNK["text"][c["char_start"] - _CHUNK["char_start"]:c["char_end"] - _CHUNK["char_start"]]
        self.assertIn("March 14, 2024", local)


class TestNormalizationNoFalseReject(unittest.TestCase):
    def test_span_differing_by_reflow_and_hyphenation_still_verifies(self):
        # The manifest-style span is single-spaced with a real hyphen; the chunk text
        # wrapped it as "twenty-\nfour". Must still verify.
        ans = 'It renews for twenty-four (24) months [chunk: C1, span: "renews for twenty-four (24) months"].'
        out = verify_answer(ans, [_CHUNK])
        self.assertEqual(out["rejected_claims"], [])
        self.assertEqual(len(out["citations"]), 1)


class TestTrueNegativeFabricated(unittest.TestCase):
    def test_span_in_no_retrieved_chunk_is_rejected_and_surfaced(self):
        ans = 'The penalty is $1,000,000 [chunk: C1, span: "a liquidated penalty of $1,000,000 per breach"].'
        out = verify_answer(ans, [_CHUNK])
        self.assertEqual(out["citations"], [])
        self.assertEqual(len(out["rejected_claims"]), 1)
        self.assertIn("does not overlap", out["rejected_claims"][0]["reason"])


class TestTrueNegativeMisPaged(unittest.TestCase):
    def test_right_text_attributed_to_wrong_chunk_is_rejected(self):
        # Span belongs to C1, but the model attributes it to C2 (different page).
        c2 = {"chunk_id": "C2", "source_filename": "nimbus_pemberton_msa.pdf", "page_number": 2,
              "char_start": 0, "char_end": 50, "text": "ARTICLE 4 - FEES. The monthly fee is $5,000."}
        ans = 'See [chunk: C2, span: "effective as of March 14, 2024"].'
        out = verify_answer(ans, [_CHUNK, c2])
        self.assertEqual(out["citations"], [])
        self.assertEqual(len(out["rejected_claims"]), 1)
        self.assertEqual(out["rejected_claims"][0]["asserted_chunk"], "C2")


class TestRefusalPathClean(unittest.TestCase):
    def test_refusal_has_no_claims(self):
        out = verify_answer(REFUSAL, [_CHUNK])
        self.assertEqual(out["citations"], [])
        self.assertEqual(out["rejected_claims"], [])


# --- M2-8a: escape-aware normalization (html.unescape + backslash-strip) ----------
# Real M2-8 grounding chunks (greenfield_castellano_lease.pdf p1) whose text carries
# real double-quotes + PDF reflow newlines. The model's spans escaped those quotes
# (F-014 backslash \" , F-016 HTML entity &quot;) which the M2-6 normalization did
# not cover -> truthful, correctly-grounded spans were false-rejected. M2-8a recovers
# them WITHOUT making the verifier accept any fabrication.
_LEASE_C1 = {
    "chunk_id": "C1", "source_filename": "greenfield_castellano_lease.pdf", "page_number": 1,
    "char_start": 40, "char_end": 264,
    "text": ('# COMMERCIAL LEASE AGREEMENT\nThis Commercial Lease Agreement (this "Lease") is '
             'made between Greenfield \nProperty Holdings LLC ("Landlord") and Yara Castellano, '
             'an individual doing \nbusiness as Castellano Studios ("Tenant").\n'),
}
_LEASE_C3 = {
    "chunk_id": "C3", "source_filename": "greenfield_castellano_lease.pdf", "page_number": 1,
    "char_start": 264, "char_end": 414,
    "text": ('## SECTION 1 — PREMISES\n1.1 Landlord leases to Tenant the premises located at '
             '1147 Aldergrove Avenue, \nUnit 3B, Crestwood, OH 44122 (the "Premises").\n'),
}


class TestEscapedSpansVerify(unittest.TestCase):
    def test_f014_backslash_escaped_quotes_in_span_verify(self):
        # F-014: model span = Greenfield Property Holdings LLC (\"Landlord\")
        span = r'Greenfield Property Holdings LLC (\"Landlord\")'
        ans = ('The Landlord is Greenfield Property Holdings LLC '
               '[document: greenfield_castellano_lease.pdf, page: 1, chunk: C1, '
               'span: "' + span + '"].')
        out = verify_answer(ans, [_LEASE_C1])
        self.assertEqual(out["rejected_claims"], [])
        self.assertEqual(len(out["citations"]), 1)
        c = out["citations"][0]
        self.assertEqual(c["page"], 1)
        self.assertEqual(c["filename"], "greenfield_castellano_lease.pdf")
        # verified offsets bound the real (unescaped) text on the page
        self.assertGreaterEqual(c["char_start"], _LEASE_C1["char_start"])
        self.assertLessEqual(c["char_end"], _LEASE_C1["char_end"])

    def test_f016_html_entity_quotes_in_span_verify(self):
        # F-016: model span used &quot; HTML entities around Premises
        span = ('1.1 Landlord leases to Tenant the premises located at 1147 Aldergrove Avenue, '
                'Unit 3B, Crestwood, OH 44122 (the &quot;Premises&quot;)')
        ans = ('The premises are at 1147 Aldergrove Avenue '
               '[document: greenfield_castellano_lease.pdf, page: 1, chunk: C3, '
               'span: "' + span + '"].')
        out = verify_answer(ans, [_LEASE_C3])
        self.assertEqual(out["rejected_claims"], [])
        self.assertEqual(len(out["citations"]), 1)
        self.assertEqual(out["citations"][0]["page"], 1)


class TestEscapedFabricationStillRejected(unittest.TestCase):
    def test_fabricated_span_with_html_entities_is_still_rejected(self):
        # The escape-aware normalization must only recover truthful escaped spans, never
        # let a fabrication through: this entity-laden span's text is in no chunk.
        ans = ('The penalty is huge [document: greenfield_castellano_lease.pdf, page: 1, '
               'chunk: C1, span: "a &quot;liquidated penalty&quot; of $9,999,999 per breach"].')
        out = verify_answer(ans, [_LEASE_C1])
        self.assertEqual(out["citations"], [])
        self.assertEqual(len(out["rejected_claims"]), 1)
        self.assertIn("does not overlap", out["rejected_claims"][0]["reason"])

    def test_backslash_escaped_fabrication_is_still_rejected(self):
        ans = ('See [document: greenfield_castellano_lease.pdf, page: 1, chunk: C1, '
               'span: "the \\"Subtenant\\" Marcus Webb of Aldergrove Holdings"].')
        out = verify_answer(ans, [_LEASE_C1])
        self.assertEqual(out["citations"], [])
        self.assertEqual(len(out["rejected_claims"]), 1)
        self.assertIn("does not overlap", out["rejected_claims"][0]["reason"])


class TestRealPresentFactsVerifyEndToEnd(unittest.TestCase):
    def test_f004_f009_f046_verify_against_correct_chunk(self):
        for fid, matter in (("F-004", PEMBERTON), ("F-009", PEMBERTON),
                            ("F-046", "Tessaro v. Brightwater Mutual")):
            f = _fact(fid)
            res = answer(_q(fid), matter=matter)
            self.assertTrue(res["citations"], f"{fid}: nothing verified")
            self.assertTrue(
                any(c["filename"] == f["filename"] and int(c["page"]) == f["page_number"]
                    and "char_start" in c and "char_end" in c for c in res["citations"]),
                f"{fid}: no verified citation for {f['filename']} p{f['page_number']}: {res['citations']}",
            )


class TestLoopbackOnlyEgress(unittest.TestCase):
    def test_answer_with_verification_is_loopback_only(self):
        import socket
        original = socket.socket.connect
        seen = []

        def recording_connect(self, address, *a, **k):
            seen.append(address)
            return original(self, address, *a, **k)

        socket.socket.connect = recording_connect
        try:
            answer(_q("F-001"), matter=PEMBERTON)
        finally:
            socket.socket.connect = original
        for addr in seen:
            host = addr[0] if isinstance(addr, tuple) else str(addr)
            self.assertIn(host, ("127.0.0.1", "::1", "localhost"), f"non-loopback egress: {addr}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
