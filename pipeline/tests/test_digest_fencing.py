"""M-2 fence: matter_facts is display-layer only this cycle. The grounded answer
path must have no route to the digest — no import, no table read. If a future
fact-router diff touches this, it must come with its own full 63/63 gate run."""

import inspect
import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import answering  # noqa: E402
import retrieval  # noqa: E402
import verifier  # noqa: E402


class TestDigestFencing(unittest.TestCase):
    def test_answer_path_never_touches_digest(self):
        for mod in (answering, verifier, retrieval):
            src = inspect.getsource(mod)
            for token in ("import digest", "matter_facts", "fact_review",
                          "routes_digest"):
                self.assertNotIn(token, src,
                                 f"{mod.__name__} references {token} — digest fence broken")

    def test_digest_accessors_require_matter(self):
        import catalog
        for fn in (catalog.facts_for_matter, catalog.reviews_for_matter,
                   catalog.prune_orphan_reviews):
            with self.assertRaises(ValueError):
                fn("")


if __name__ == "__main__":
    unittest.main(verbosity=2)
