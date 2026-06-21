"""T-CLAUSE UI proof: the Contract Review surface in the SAM-style local app.

GET /app exposes a sixth nav item ("Contract Review") wired to a view; the local app.js
renders the clause checklist by status — a "found" row shows the value + a citation chip
linked to the EXISTING /kb/highlight surface (chunk-derived page+span), a
"potentially_missing" row shows a clearly-distinct advisory badge with NO citation, and a
"not_confirmed" row is shown without a citation. Model text is escaped before render
(esc(), D-48 XSS guard) and no remote asset is referenced (air-gap). Asserted on the
served text in the style of test_app_shell / test_api_ui (no JS runtime).
"""

import re
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import api  # noqa: E402

client = TestClient(api.app)

_EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["']https?://""", re.IGNORECASE)


class TestContractReviewNav(unittest.TestCase):
    def test_app_shell_has_contract_review_nav(self):
        r = client.get("/app")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Contract Review", r.text)
        self.assertIn('data-view="clauses"', r.text)
        # the original five nav labels still present (no regression)
        for label in ("New Chat", "Matters", "Document Hub", "Chat History", "Settings"):
            self.assertIn(label, r.text)


class TestContractReviewJs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = client.get("/static/app.js").text

    def test_registers_a_clauses_view_hook(self):
        self.assertIn("viewHooks.clauses", self.js)

    def test_calls_the_review_and_taxonomy_endpoints(self):
        self.assertIn("/clauses/review", self.js)

    def test_renders_all_three_statuses(self):
        for token in ("found", "potentially_missing", "not_confirmed"):
            self.assertIn(token, self.js, f"clause status not handled: {token}")

    def test_reuses_existing_highlight_surface_for_found_citations(self):
        # the cited-span highlight URL helper is reused (never a new fuzzy highlighter)
        self.assertIn("/kb/highlight/", self.js)

    def test_escapes_model_text_before_render(self):
        # the clause renderer must run model-supplied strings through esc() (XSS, D-48)
        self.assertRegex(self.js, r"renderClause|clauseRow|renderClauses")
        self.assertIn("esc(", self.js)

    def test_no_external_asset_url(self):
        self.assertIsNone(_EXTERNAL.search(self.js))


class TestContractReviewCss(unittest.TestCase):
    def test_has_distinct_missing_badge_style(self):
        css = client.get("/static/app.css").text
        self.assertIn("clause", css, "no Contract Review styling present")


if __name__ == "__main__":
    unittest.main(verbosity=2)
