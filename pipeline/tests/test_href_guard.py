"""Apostrophe guard on every single-quoted highlight href (council 2026-07-11 Move 1).

encodeURIComponent leaves ' raw, so a span like "party's obligation" would end the
href='...' attribute early — the same breakout class fixed in the overview (ovHref/
calHref, test_digest_ui). These assert the three remaining builders carry the guard:
citationThumb, highlightUrl, and the Find-in-documents hit link. Static assertions
only, matching the repo idiom for app.js."""

import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
APP_JS = (PIPELINE_DIR / "static" / "app.js").read_text()

GUARD = 'replace(/\'/g, "%27")'


class TestHighlightHrefApostropheGuard(unittest.TestCase):
    def _fn(self, name, span=600):
        i = APP_JS.index("function " + name)
        return APP_JS[i:i + span]

    def test_citation_thumb_guarded(self):
        self.assertIn(GUARD, self._fn("citationThumb"))

    def test_highlight_url_guarded(self):
        self.assertIn(GUARD, self._fn("highlightUrl", 320))

    def test_search_hit_href_guarded(self):
        # The Find-in-documents hit link builds its href inline; scope from the
        # search fetch to the hit-panel markup.
        i = APP_JS.index("/search?q=")
        seg = APP_JS[i:APP_JS.index("search-hit", i) + 50]
        self.assertIn(GUARD, seg)


if __name__ == "__main__":
    unittest.main()
