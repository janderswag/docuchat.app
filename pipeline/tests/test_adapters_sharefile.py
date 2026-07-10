"""ShareFile adapter proofs — password-grant token mint (form-encoded), the
two-hostname split (oauth on {sub}.sharefile.com, API on {sub}.sf-api.com),
OData folder walk with $top/$skip paging, and download-by-redirect."""

import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import connectors  # noqa: E402
from tests.test_adapters import (FakeResponse, MockVendor,  # noqa: E402
                                 fetch_contract_check, service_contract_check)

CREDS = {"subdomain": "Pemberton", "username": "jake@firm.example",
         "password": "pw", "client_id": "cid", "client_secret": "cs"}

TOKEN = FakeResponse(json_data={"access_token": "tok8h", "refresh_token": "r",
                                "expires_in": 28800, "subdomain": "pemberton",
                                "apicp": "sf-api.com"})


def feed(entries):
    return FakeResponse(json_data={"value": entries})


FILE_A = {"odata.type": "ShareFile.Api.Models.File", "Id": "fi-a",
          "FileName": "Retainer.pdf", "Name": "Retainer agreement",
          "CreationDate": "2026-06-01T10:00:00Z",
          "CreatorNameShort": "J. Doe", "ProgenyEditDate": "2026-06-02T10:00:00Z"}
FOLDER = {"odata.type": "ShareFile.Api.Models.Folder", "Id": "fo-1",
          "Name": "Discovery", "FileName": "Discovery"}
FILE_B = {"odata.type": "ShareFile.Api.Models.File", "Id": "fi-b",
          "FileName": "Exhibit 3.docx", "CreationDate": "2026-06-03T10:00:00Z",
          "CreatorNameShort": "A. Roe"}


class TestShareFile(unittest.TestCase):
    def _mod(self):
        from connectors import sharefile
        return sharefile

    def test_service_metadata(self):
        service_contract_check(self, self._mod())

    def test_password_grant_is_form_encoded_on_the_oauth_host(self):
        routes = [
            ("POST", "https://pemberton.sharefile.com/oauth/token", TOKEN),
            ("GET", "https://pemberton.sf-api.com/sf/v3/Sessions",
             FakeResponse(json_data={"Principal": {"Email": "jake@firm.example"}})),
        ]
        with MockVendor(routes) as v:
            label = self._mod().test(CREDS)
        self.assertIn("jake@firm.example", label)
        mint = v.calls[0]
        self.assertEqual(mint["json_body"], None)
        self.assertEqual(mint["form_body"]["grant_type"], "password")
        self.assertEqual(mint["form_body"]["username"], "jake@firm.example")
        api_call = v.calls[1]
        self.assertEqual(api_call["headers"]["Authorization"], "Bearer tok8h")

    def test_rejected_grant_maps_to_auth_error(self):
        bad = FakeResponse(json_data={"error": "invalid_grant"})
        with MockVendor([("POST", "https://pemberton.sharefile.com/oauth/token",
                          bad)]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(CREDS)

    def test_list_walks_folders_and_pages(self):
        pages = {"allshared": feed([FILE_A, FOLDER]), "fo-1": feed([FILE_B])}

        def route(call):
            for key, resp in pages.items():
                if f"Items({key})" in call["url"]:
                    return resp
            return feed([])
        with MockVendor([
            ("POST", "https://pemberton.sharefile.com/oauth/token", TOKEN),
            ("GET", "https://pemberton.sf-api.com/sf/v3/Items", route),
        ]) as v:
            items = self._mod().list_items(CREDS)
        names = sorted(i["name"] for i in items)
        self.assertEqual(names, ["Exhibit 3.docx", "Retainer.pdf"])
        # one token mint for the whole operation
        mints = [c for c in v.calls if "oauth/token" in c["url"]]
        self.assertEqual(len(mints), 1)
        sub = [i for i in items if i["id"] == "fi-b"][0]
        self.assertEqual(sub["meta"]["path"], "/Discovery")

    def test_fetch_downloads_bytes(self):
        with MockVendor([
            ("POST", "https://pemberton.sharefile.com/oauth/token", TOKEN),
            ("GET", "https://pemberton.sf-api.com/sf/v3/Items(fi-a)/Download",
             FakeResponse(content=b"%PDF-1.7 synthetic")),
        ]):
            item = {"id": "fi-a", "name": "Retainer.pdf", "kind": "file",
                    "modified": "2026-06-02",
                    "meta": {"path": "", "author": "J. Doe",
                             "created": "2026-06-01T10:00:00Z"}}
            name, body, prov = self._mod().fetch_item(CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(name, "Retainer.pdf")
        self.assertEqual(prov["author"], "J. Doe")


class TestFormBodySeam(unittest.TestCase):
    def test_request_passes_form_body_as_urlencoded(self):
        import httpx
        seen = {}

        def handler(request):
            seen["content_type"] = request.headers.get("content-type", "")
            seen["body"] = request.content.decode()
            return httpx.Response(200, json={"ok": True})
        orig = httpx.request

        def fake_request(method, url, **kw):
            with httpx.Client(transport=httpx.MockTransport(handler)) as c:
                return c.request(method, url, data=kw.get("data"),
                                 json=kw.get("json"), headers=kw.get("headers"))
        httpx.request = fake_request
        try:
            connectors.request("POST", "https://vendor.test/oauth/token",
                               form_body={"grant_type": "password", "a": "b"})
        finally:
            httpx.request = orig
        self.assertIn("application/x-www-form-urlencoded", seen["content_type"])
        self.assertIn("grant_type=password", seen["body"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
