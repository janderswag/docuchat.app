"""Council 2026-07-11 Move 5 — "Every mention" legibility.

The exhaustive zero-LLM enumeration surface gets a name that explains itself,
promotion to the top of the Document Hub, two labeled mode choices, a
repointed /find (exhaustive, not a chat template), and a cross-link from chat
citations at the moment of need. Static assertions, repo idiom."""

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import api  # noqa: E402

client = TestClient(api.app)


class TestEveryMentionUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = client.get("/static/app.js").text

    def test_renamed_and_promoted_above_unfiled(self):
        self.assertIn("<b>Every mention</b>", self.js)
        self.assertNotIn("<b>Find in documents</b>", self.js)
        hub = self.js[self.js.index("function buildHub"):]
        self.assertLess(hub.index("Every mention"), hub.index("<b>Unfiled</b>"),
                        "panel must sit above the filing sections")

    def test_two_labeled_mode_choices(self):
        self.assertIn("Every mention — exact text, counted", self.js)
        self.assertIn("Best match — ranked, wording unknown", self.js)

    def test_find_command_repointed(self):
        i = self.js.index('item.cmd === "find"')
        seg = self.js[i:i + 700]
        self.assertIn("openEveryMention", seg)
        self.assertNotIn("Where do this matter's documents discuss", seg)
        # palette description says what it now does
        self.assertIn("Every mention of ", self.js)

    def test_citation_cross_link(self):
        self.assertIn("every-mention-link", self.js)
        self.assertIn("See every mention of the cited passage", self.js)
        # the probe is escaped before entering the data attribute
        i = self.js.index("every-mention-link' data-q=")
        self.assertIn("esc(probe)", self.js[i - 200:i + 200])

    def test_open_helper_targets_mentions_mode(self):
        i = self.js.index("window.openEveryMention")
        seg = self.js[i:i + 700]
        self.assertIn('"mentions"', seg)
        self.assertIn('showView("hub")', seg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
