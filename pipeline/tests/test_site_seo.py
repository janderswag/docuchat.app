"""D-61 SEO/GEO/AEO foundation — machine-readable discovery + structured data guards.

Phase A (machine-only, pushed to prod): robots.txt, sitemap.xml, llms.txt / llms-full.txt,
canonical, and JSON-LD (Organization + SoftwareApplication).
Phase B (customer-facing, held for owner approval): Open Graph / Twitter cards + OG image,
the visible FAQ + its FAQPage JSON-LD (visible-content parity), the comparison table, and the
GEO stat in visible copy.

Pure file/string/JSON/XML checks — they never touch the pipeline, verifier, or any store.
"""

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SITE = REPO_ROOT / "site"

APEX = "https://docuchat.app/"
LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


def _read(name):
    return (SITE / name).read_text(encoding="utf-8")


def _ldjson_blocks(html):
    """Every <script type=application/ld+json> block, parsed to a dict (raises on bad JSON)."""
    return [json.loads(m) for m in LDJSON_RE.findall(html)]


class TestPhaseAMachineFiles(unittest.TestCase):
    def test_robots_allows_and_points_at_sitemap(self):
        r = _read("robots.txt")
        self.assertRegex(r, r"User-agent:\s*\*")
        self.assertRegex(r, r"Allow:\s*/")
        self.assertIn("Sitemap: https://docuchat.app/sitemap.xml", r)

    def test_robots_welcomes_ai_crawlers(self):
        r = _read("robots.txt")
        for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot"):
            self.assertIn(bot, r, f"robots.txt does not name {bot}")

    def test_sitemap_is_valid_xml_with_apex(self):
        root = ET.fromstring(_read("sitemap.xml"))
        self.assertTrue(root.tag.endswith("urlset"), "sitemap root is not <urlset>")
        locs = [e.text for e in root.iter() if e.tag.endswith("loc")]
        self.assertIn(APEX, locs, "sitemap.xml missing the apex URL")

    def test_llms_files_exist(self):
        self.assertTrue((SITE / "llms.txt").is_file(), "site/llms.txt missing")
        self.assertTrue((SITE / "llms-full.txt").is_file(), "site/llms-full.txt missing")
        self.assertTrue(_read("llms.txt").startswith("# docuchat"), "llms.txt missing H1")

    def test_canonical_present(self):
        self.assertIn('<link rel="canonical" href="https://docuchat.app/">', _read("index.html"))

    def test_org_and_softwareapplication_jsonld_present_and_valid(self):
        blocks = _ldjson_blocks(_read("index.html"))
        types = {b.get("@type") for b in blocks}
        self.assertIn("Organization", types, "Organization JSON-LD missing/invalid")
        self.assertIn("SoftwareApplication", types, "SoftwareApplication JSON-LD missing/invalid")
        app = next(b for b in blocks if b.get("@type") == "SoftwareApplication")
        # sanity: the offer is free and the download points at the releases page
        self.assertEqual(app["offers"]["price"], "0")
        self.assertIn("releases", app["downloadUrl"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
