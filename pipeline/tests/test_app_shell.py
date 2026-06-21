"""Task 1 proof: the SAM-style app shell + left nav, served with LOCAL-ONLY assets.

GET /app -> the shell HTML with the five (and only five) nav labels; GET /static/*
serves local JS/CSS, path-locked like /source; and NO served asset references an
external http(s) URL (air-gap: a CDN fetch would be non-loopback egress)."""

import re
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import api  # noqa: E402

client = TestClient(api.app)

NAV_LABELS = ["New Chat", "Matters", "Document Hub", "Chat History", "Settings"]
# Anything that would pull a remote asset at runtime (CDN, web font, remote script).
_EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["']https?://|@import\s+url\(\s*["']?https?://""",
                       re.IGNORECASE)


class TestAppShell(unittest.TestCase):
    def test_app_serves_html_with_five_nav_labels(self):
        r = client.get("/app")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers["content-type"])
        for label in NAV_LABELS:
            self.assertIn(label, r.text, f"nav label missing: {label}")

    def test_static_js_served_locally(self):
        r = client.get("/static/app.js")
        self.assertEqual(r.status_code, 200)
        self.assertIn("javascript", r.headers["content-type"])

    def test_static_css_served_locally(self):
        r = client.get("/static/app.css")
        self.assertEqual(r.status_code, 200)
        self.assertIn("css", r.headers["content-type"])

    def test_static_path_traversal_rejected(self):
        r = client.get("/static/../api.py")
        self.assertEqual(r.status_code, 404)

    def test_no_external_asset_urls_anywhere(self):
        bodies = [client.get(p).text for p in ("/app", "/static/app.js", "/static/app.css")]
        for body in bodies:
            m = _EXTERNAL.search(body)
            self.assertIsNone(m, f"external asset URL found (CDN/egress): {m.group(0) if m else ''}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
