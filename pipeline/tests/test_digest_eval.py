"""G-DIG scorer: recall per fact type against a hand-labeled inventory, matched
via the verifier's normalization; drop counts reported; exit code from targets."""

import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import run_digest_eval  # noqa: E402


class TestScorer(unittest.TestCase):
    def test_recall_by_type(self):
        inventory = [
            {"doc": "a.pdf", "fact_type": "party", "span_contains": "pemberton logistics"},
            {"doc": "a.pdf", "fact_type": "party", "span_contains": "nimbus analytics"},
            {"doc": "a.pdf", "fact_type": "amount", "span_contains": "$28,000"},
        ]
        extracted = {("a.pdf", "party"): ["Pemberton Logistics Inc. (\"Client\")"],
                     ("a.pdf", "amount"): []}
        recall = run_digest_eval.score(inventory, extracted)
        self.assertEqual(recall["party"], {"hit": 1, "total": 2})
        self.assertEqual(recall["amount"], {"hit": 0, "total": 1})

    def test_span_inside_needle_counts_as_hit(self):
        # The model excerpts a tighter span than the hand-labeled fragment: the
        # extracted span is a genuine substring of the longer inventory needle.
        inventory = [
            {"doc": "b.pdf", "fact_type": "date",
             "span_contains": "entered into and effective as of March 14, 2024 "
                               "(the Effective Date)"},
        ]
        extracted = {("b.pdf", "date"): ["March 14, 2024 (the Effective Date)"]}
        recall = run_digest_eval.score(inventory, extracted)
        self.assertEqual(recall["date"], {"hit": 1, "total": 1})

    def test_degenerate_short_span_is_not_a_hit(self):
        # A bare year is a substring of the needle too, but at norm length 4 it's
        # below the 12-char floor, so it must not count as a hit.
        inventory = [
            {"doc": "b.pdf", "fact_type": "date",
             "span_contains": "entered into and effective as of March 14, 2024 "
                               "(the Effective Date)"},
        ]
        extracted = {("b.pdf", "date"): ["2024"]}
        recall = run_digest_eval.score(inventory, extracted)
        self.assertEqual(recall["date"], {"hit": 0, "total": 1})

    def test_targets_gate(self):
        self.assertTrue(run_digest_eval.meets_targets(
            {"party": {"hit": 9, "total": 10}}, {"party": 0.90}))
        self.assertFalse(run_digest_eval.meets_targets(
            {"party": {"hit": 8, "total": 10}}, {"party": 0.90}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
