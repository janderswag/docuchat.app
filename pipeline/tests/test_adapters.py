"""Per-adapter proofs (v0.3.0, D-81) — every adapter against its vendor's
DOCUMENTED response shapes (from the 2026-07-10 research pass), mocked at the
connectors.request layer. No network. Each adapter suite proves:

  1. SERVICE metadata is complete (fields, key_steps, docs_url, category).
  2. test() sends the documented auth and returns an account label.
  3. list_items() paginates and maps the documented list shape.
  4. fetch_item() returns (supported filename, bytes, provenance with the
     D-80 fields available from that vendor).
  5. A 401 surfaces ConnectorAuthError (the framework taxonomy).

Shared harness: MockVendor patches connectors.request with canned
(method, url-prefix) -> response entries and records every call.
"""

import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import connectors  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json = json_data
        self.content = content if content else (b"" if json_data is None else b"{}")

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class MockVendor:
    """Patch connectors.request with canned routes; record calls for auth checks."""

    def __init__(self, routes):
        self.routes = routes            # [(method, url_prefix, response_or_fn)]
        self.calls = []                 # (method, url, headers, params)

    def __enter__(self):
        self._orig = connectors.request

        def fake(method, url, *, headers=None, params=None, json_body=None,
                 timeout=None, auth=None, follow_redirects=True):
            self.calls.append({"method": method, "url": url,
                               "headers": headers or {}, "params": params or {},
                               "json_body": json_body, "auth": auth})
            for m, prefix, resp in self.routes:
                if m == method and url.startswith(prefix):
                    r = resp(self.calls[-1]) if callable(resp) else resp
                    if r.status_code == 401:
                        raise connectors.ConnectorAuthError("the service rejected this key")
                    if r.status_code >= 400:
                        raise connectors.ConnectorError(f"HTTP {r.status_code}")
                    return r
            raise AssertionError(f"unexpected call: {method} {url}")
        connectors.request = fake
        return self

    def __exit__(self, *exc):
        connectors.request = self._orig


def service_contract_check(case, mod):
    svc = mod.SERVICE
    for key in ("slug", "name", "category", "blurb", "fields", "key_steps",
                "docs_url"):
        case.assertTrue(svc.get(key) not in (None, "", []), f"SERVICE.{key} missing")
    for f in svc["fields"]:
        case.assertIn("key", f)
        case.assertIn("label", f)
    case.assertGreaterEqual(len(svc["key_steps"]), 2,
                            "key_steps must actually guide the user")


ALLOWED = {".pdf", ".docx", ".txt", ".md", ".eml", ".html", ".htm", ".vtt",
           ".srt", ".csv", ".json"}


def fetch_contract_check(case, filename, body, prov):
    case.assertTrue(any(filename.lower().endswith(s) for s in ALLOWED),
                    f"{filename} is not an ingestible type")
    case.assertIsInstance(body, bytes)
    case.assertTrue(body)
    case.assertIn("title", prov)


class TestFathom(unittest.TestCase):
    CREDS = {"api_key": "fk-test"}
    MEETING = {
        "recording_id": "rec_1", "title": "Pemberton kickoff",
        "created_at": "2026-07-01T10:00:00Z",
        "recorded_by": {"email": "jake@firm.example"},
        "share_url": "https://fathom.video/share/x",
        "transcript": [
            {"speaker": "Jake", "text": "Good morning.", "timestamp": "00:00"},
            {"speaker": "Ana", "text": "Morning, let's begin.", "timestamp": "00:05"},
        ],
        "default_summary": "Kickoff summary.",
    }

    def _mod(self):
        from connectors import fathom
        return fathom

    def test_service_metadata(self):
        service_contract_check(self, self._mod())

    def test_auth_header_and_label(self):
        page = FakeResponse(json_data={"items": [self.MEETING], "next_cursor": None})
        with MockVendor([("GET", "https://api.fathom.ai/external/v1/meetings", page)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("meetings", label)
        self.assertEqual(v.calls[0]["headers"]["X-Api-Key"], "fk-test")
        self.assertNotIn("Authorization", v.calls[0]["headers"])  # documented gotcha

    def test_list_paginates_by_cursor(self):
        pages = iter([
            FakeResponse(json_data={"items": [self.MEETING], "next_cursor": "c2"}),
            FakeResponse(json_data={"items": [dict(self.MEETING, recording_id="rec_2",
                                                   transcript=[])],
                                    "next_cursor": None}),
        ])
        with MockVendor([("GET", "https://api.fathom.ai/external/v1/meetings",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["rec_1", "rec_2"])
        self.assertEqual(v.calls[1]["params"].get("cursor"), "c2")
        self.assertEqual(items[0]["kind"], "transcript")
        self.assertEqual(items[1]["kind"], "summary")
        # async-delivery gotcha: destination_url must NEVER be sent
        for c in v.calls:
            self.assertNotIn("destination_url", c["params"])

    def test_fetch_renders_vtt_with_speakers(self):
        item = {"id": "rec_1", "name": "Pemberton kickoff", "kind": "transcript",
                "modified": "2026-07-01", "meta": self.MEETING}
        name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        text = body.decode()
        self.assertIn("WEBVTT", text)
        self.assertIn("<v Jake>Good morning.", text)
        self.assertIn("00:00:05.000", text)
        self.assertEqual(prov["author"], "jake@firm.example")
        self.assertEqual(prov["speakers"], ["Ana", "Jake"])

    def test_fetch_falls_back_to_summary_md(self):
        meta = dict(self.MEETING, transcript=[])
        item = {"id": "rec_1", "name": "Pemberton kickoff", "kind": "summary",
                "modified": "2026-07-01", "meta": meta}
        name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".md"))
        self.assertIn(b"Kickoff summary.", body)

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", "https://api.fathom.ai", FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
