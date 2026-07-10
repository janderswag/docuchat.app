"""CRM adapter proofs (v0.3.0, D-81) — HubSpot, Zoho CRM, and Pipedrive
against their vendors' DOCUMENTED response shapes (research_crm.json,
2026-07-10), mocked at the connectors.request layer via the shared harness in
test_adapters. No network. Each suite proves the five per-adapter contracts
plus the vendor-specific flows: HubSpot's signed-url two-step for file bytes,
Zoho's prepare() grant-code exchange and refresh-token minting (one mint per
operation, Zoho-oauthtoken header), and Pipedrive's x-api-token header with
v1 start/limit pagination and /download bytes.
"""

import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import connectors  # noqa: E402

from tests.test_adapters import (FakeResponse, MockVendor,  # noqa: E402
                                 fetch_contract_check, service_contract_check)

HS = "https://api.hubapi.com"


class TestHubSpot(unittest.TestCase):
    CREDS = {"access_token": "pat-na1-test"}
    NOTE = {
        "id": "301",
        "createdAt": "2026-07-01T10:00:00Z",
        "updatedAt": "2026-07-02T09:00:00Z",
        "properties": {
            "hs_note_body": "<p>Called the client about the "
                            "<b>Pemberton</b> lease.</p>",
            "hs_attachment_ids": "9001",
            "hs_timestamp": "2026-07-01T10:00:00Z",
            "hs_createdate": "2026-07-01T10:00:00Z",
            "hs_lastmodifieddate": "2026-07-02T09:00:00Z",
            "hubspot_owner_id": "77",
        },
        "associations": {"deals": {"results": [{"id": "555"}]}},
    }
    FILE = {"id": "9001", "name": "lease-draft", "extension": "pdf",
            "createdAt": "2026-06-30T08:00:00Z",
            "updatedAt": "2026-06-30T08:00:00Z"}

    def _mod(self):
        from connectors import hubspot
        return hubspot

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        self.assertEqual(self._mod().SERVICE["slug"], "hubspot")

    def test_bearer_auth_and_label(self):
        page = FakeResponse(json_data={"portalId": 4242})
        with MockVendor([("GET", f"{HS}/account-info/v3/details", page)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("4242", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer pat-na1-test")

    def test_list_paginates_notes_and_files(self):
        note_pages = iter([
            FakeResponse(json_data={"results": [self.NOTE],
                                    "paging": {"next": {"after": "n2"}}}),
            FakeResponse(json_data={"results": [dict(self.NOTE, id="302")]}),
        ])
        file_pages = iter([
            FakeResponse(json_data={"results": [self.FILE],
                                    "paging": {"next": {"after": "f2"}}}),
            FakeResponse(json_data={"results": []}),
        ])
        with MockVendor([
            ("GET", f"{HS}/crm/v3/objects/notes", lambda c: next(note_pages)),
            ("GET", f"{HS}/files/v3/files/search", lambda c: next(file_pages)),
        ]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items],
                         ["note:301", "note:302", "file:9001"])
        self.assertEqual(items[2]["name"], "lease-draft.pdf")
        note_calls = [c for c in v.calls if "/objects/notes" in c["url"]]
        self.assertEqual(note_calls[1]["params"].get("after"), "n2")
        self.assertIn("hs_note_body", note_calls[0]["params"]["properties"])
        self.assertIn("hs_attachment_ids", note_calls[0]["params"]["properties"])
        file_calls = [c for c in v.calls if "/files/search" in c["url"]]
        self.assertEqual(file_calls[1]["params"].get("after"), "f2")

    def test_fetch_note_renders_md_with_associations(self):
        item = {"id": "note:301",
                "name": "Called the client about the Pemberton lease.",
                "kind": "note", "modified": "2026-07-02T09:00:00Z",
                "meta": self.NOTE}
        name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".md"))
        text = body.decode()
        self.assertIn("Called the client about the Pemberton lease.", text)
        self.assertIn("deals 555", text)
        self.assertNotIn("<p>", text)
        self.assertEqual(prov["date"], "2026-07-01T10:00:00Z")
        self.assertEqual(prov["modified"], "2026-07-02T09:00:00Z")
        self.assertEqual(prov["author"], "77")

    def test_fetch_file_signed_url_two_step(self):
        item = {"id": "file:9001", "name": "lease-draft.pdf", "kind": "file",
                "modified": "2026-06-30T08:00:00Z", "meta": self.FILE}
        with MockVendor([
            ("GET", f"{HS}/files/v3/files/9001/signed-url",
             FakeResponse(json_data={"url": "https://cdn.hubspot.test/signed/abc"})),
            ("GET", "https://cdn.hubspot.test/signed/abc",
             FakeResponse(content=b"%PDF-1.7 hubspot")),
        ]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(name, "lease-draft.pdf")
        self.assertEqual(body, b"%PDF-1.7 hubspot")
        self.assertIn("/files/v3/files/9001/signed-url", v.calls[0]["url"])
        self.assertEqual(v.calls[1]["url"], "https://cdn.hubspot.test/signed/abc")
        # the signed URL is itself the credential; the token must not leak
        self.assertNotIn("Authorization", v.calls[1]["headers"])

    def test_bad_token_maps_to_auth_error(self):
        with MockVendor([("GET", HS, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


ZACC = "https://accounts.zoho.com"
ZAPI = "https://www.zohoapis.com"


class TestZoho(unittest.TestCase):
    RAW = {"client_id": "1000.CID", "client_secret": "zsec",
           "grant_code": "1000.grant", "data_center": "com"}
    CREDS = {"client_id": "1000.CID", "client_secret": "zsec",
             "refresh_token": "1000.refresh", "data_center": "com"}
    LEAD = {"id": "500", "Last_Name": "Pemberton",
            "Modified_Time": "2026-07-01T10:00:00+00:00"}
    ATT_FILE = {"id": "900", "File_Name": "engagement-letter.pdf",
                "Size": "1024", "Created_Time": "2026-07-01T10:00:00+00:00",
                "Modified_Time": "2026-07-01T10:00:00+00:00",
                "Owner": {"name": "Jake", "id": "1"}}
    ATT_LINK = {"id": "901", "File_Name": "shared doc",
                "$link_url": "https://docs.example/x",
                "Created_Time": "2026-07-01T11:00:00+00:00"}

    def _mod(self):
        from connectors import zoho
        return zoho

    def test_service_metadata(self):
        mod = self._mod()
        service_contract_check(self, mod)
        self.assertEqual(mod.SERVICE["slug"], "zoho")
        steps = " ".join(mod.SERVICE["key_steps"])
        self.assertIn("api-console.zoho", steps)
        self.assertIn("Self Client", steps)
        self.assertIn("ZohoCRM.modules.READ,ZohoCRM.settings.READ", steps)
        self.assertIn("10 minutes", mod.SERVICE["plan_note"])

    def test_prepare_exchanges_grant_code_for_refresh_token(self):
        token = FakeResponse(json_data={"access_token": "at1",
                                        "refresh_token": "1000.refresh",
                                        "api_domain": ZAPI})
        with MockVendor([("POST", f"{ZACC}/oauth/v2/token", token)]) as v:
            out = self._mod().prepare(self.RAW)
        call = v.calls[0]
        self.assertEqual(call["params"]["grant_type"], "authorization_code")
        self.assertEqual(call["params"]["code"], "1000.grant")
        self.assertEqual(call["params"]["client_id"], "1000.CID")
        self.assertEqual(call["params"]["client_secret"], "zsec")
        self.assertEqual(out, {"client_id": "1000.CID", "client_secret": "zsec",
                               "refresh_token": "1000.refresh",
                               "data_center": "com"})
        self.assertNotIn("grant_code", out)      # dead code is not sealed

    def test_prepare_expired_code_is_auth_error(self):
        # Zoho answers 200 + {"error": ...} for a dead grant code
        bad = FakeResponse(json_data={"error": "invalid_code"})
        with MockVendor([("POST", f"{ZACC}/oauth/v2/token", bad)]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().prepare(self.RAW)

    def test_data_center_routes_hosts(self):
        token = FakeResponse(json_data={"access_token": "a",
                                        "refresh_token": "r"})
        with MockVendor([("POST", "https://accounts.zoho.eu/oauth/v2/token",
                          token)]) as v:
            out = self._mod().prepare(dict(self.RAW, data_center="eu"))
        self.assertTrue(v.calls[0]["url"].startswith("https://accounts.zoho.eu/"))
        self.assertEqual(out["data_center"], "eu")

    def test_test_mints_from_refresh_and_sends_zoho_oauthtoken(self):
        with MockVendor([
            ("POST", f"{ZACC}/oauth/v2/token",
             FakeResponse(json_data={"access_token": "at-min"})),
            ("GET", f"{ZAPI}/crm/v8/org",
             FakeResponse(json_data={"org": [{"company_name": "Anderson Law"}]})),
        ]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("Anderson Law", label)
        mint = v.calls[0]
        self.assertEqual(mint["method"], "POST")
        self.assertEqual(mint["params"]["grant_type"], "refresh_token")
        self.assertEqual(mint["params"]["refresh_token"], "1000.refresh")
        self.assertEqual(v.calls[1]["headers"]["Authorization"],
                         "Zoho-oauthtoken at-min")

    def test_list_walks_modules_skips_links_one_mint(self):
        routes = [
            ("POST", f"{ZACC}/oauth/v2/token",
             FakeResponse(json_data={"access_token": "at-min"})),
            # more-specific prefix FIRST so it wins over the module route
            ("GET", f"{ZAPI}/crm/v8/Leads/500/Attachments",
             FakeResponse(json_data={"data": [self.ATT_FILE, self.ATT_LINK]})),
            ("GET", f"{ZAPI}/crm/v8/Leads",
             FakeResponse(json_data={"data": [self.LEAD]})),
            ("GET", f"{ZAPI}/crm/v8/Contacts", FakeResponse(204)),  # empty
            ("GET", f"{ZAPI}/crm/v8/Deals", FakeResponse(204)),
        ]
        with MockVendor(routes) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["Leads/500/900"])
        self.assertEqual(items[0]["name"], "engagement-letter.pdf")
        mints = [c for c in v.calls if c["method"] == "POST"]
        self.assertEqual(len(mints), 1, "one access token per operation, reused")
        urls = [c["url"] for c in v.calls if c["method"] == "GET"]
        for module in ("Leads", "Contacts", "Deals"):
            self.assertIn(f"{ZAPI}/crm/v8/{module}", urls)
        lead_list = [c for c in v.calls if c["url"] == f"{ZAPI}/crm/v8/Leads"][0]
        self.assertIn("Last_Name", lead_list["params"]["fields"])
        self.assertEqual(lead_list["params"]["per_page"], 200)
        for c in v.calls:
            if c["method"] == "GET":
                self.assertEqual(c["headers"]["Authorization"],
                                 "Zoho-oauthtoken at-min")

    def test_fetch_downloads_attachment_bytes(self):
        item = {"id": "Leads/500/900", "name": "engagement-letter.pdf",
                "kind": "attachment", "modified": "2026-07-01T10:00:00+00:00",
                "meta": {"module": "Leads", "record_id": "500",
                         "record_name": "Pemberton",
                         "attachment": self.ATT_FILE}}
        with MockVendor([
            ("POST", f"{ZACC}/oauth/v2/token",
             FakeResponse(json_data={"access_token": "at-min"})),
            ("GET", f"{ZAPI}/crm/v8/Leads/500/Attachments/900",
             FakeResponse(content=b"%PDF-1.7 zoho")),
        ]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(name, "engagement-letter.pdf")
        self.assertEqual(body, b"%PDF-1.7 zoho")
        self.assertEqual(prov["author"], "Jake")
        self.assertIn("Pemberton", prov["parent"])
        self.assertEqual(v.calls[1]["headers"]["Authorization"],
                         "Zoho-oauthtoken at-min")

    def test_revoked_refresh_token_is_auth_error(self):
        bad = FakeResponse(json_data={"error": "invalid_token"})
        with MockVendor([("POST", f"{ZACC}/oauth/v2/token", bad)]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)

    def test_api_401_maps_to_auth_error(self):
        with MockVendor([
            ("POST", f"{ZACC}/oauth/v2/token",
             FakeResponse(json_data={"access_token": "a"})),
            ("GET", ZAPI, FakeResponse(401)),
        ]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


PD = "https://andersonlaw.pipedrive.com/api"


class TestPipedrive(unittest.TestCase):
    CREDS = {"api_token": "pd-token", "company_domain": "andersonlaw"}
    NOTE = {"id": 41, "content": "<p>Discussed the <b>lease</b> terms.</p>",
            "user_id": 7, "deal_id": 3,
            "add_time": "2026-07-01 10:00:00",
            "update_time": "2026-07-02 09:00:00",
            "deal": {"title": "Pemberton lease"},
            "person": {"name": "Ana Diaz"},
            "user": {"name": "Jake Anderson"}}
    FILE = {"id": 88, "file_name": "signed-agreement.pdf", "file_type": "pdf",
            "add_time": "2026-06-30 08:00:00",
            "update_time": "2026-06-30 08:00:00",
            "added_by_user_id": 7, "deal_id": 3,
            "deal_name": "Pemberton lease", "remote_location": "pipedrive"}
    FILE_REMOTE = {"id": 89, "file_name": "linked-gdoc", "file_type": "gdoc",
                   "add_time": "2026-06-30 08:00:00",
                   "update_time": "2026-06-30 08:00:00",
                   "remote_location": "googledrive"}

    def _mod(self):
        from connectors import pipedrive
        return pipedrive

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        self.assertEqual(self._mod().SERVICE["slug"], "pipedrive")

    def test_x_api_token_header_and_label(self):
        me = FakeResponse(json_data={"success": True,
                                     "data": {"id": 7, "name": "Jake Anderson",
                                              "company_domain": "andersonlaw"}})
        with MockVendor([("GET", f"{PD}/v1/users/me", me)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("Jake Anderson", label)
        self.assertEqual(v.calls[0]["headers"]["x-api-token"], "pd-token")
        self.assertNotIn("Authorization", v.calls[0]["headers"])

    def test_list_paginates_start_limit_and_skips_remote_files(self):
        note_pages = iter([
            FakeResponse(json_data={"data": [self.NOTE], "additional_data": {
                "pagination": {"more_items_in_collection": True,
                               "next_start": 100}}}),
            FakeResponse(json_data={"data": [dict(self.NOTE, id=42)],
                                    "additional_data": {"pagination": {
                                        "more_items_in_collection": False}}}),
        ])
        files = FakeResponse(json_data={
            "data": [self.FILE, self.FILE_REMOTE],
            "additional_data": {"pagination": {
                "more_items_in_collection": False}}})
        with MockVendor([
            ("GET", f"{PD}/v1/notes", lambda c: next(note_pages)),
            ("GET", f"{PD}/v1/files", files),
        ]) as v:
            items = self._mod().list_items(self.CREDS)
        # the Drive-linked file (remote_location != pipedrive) is skipped
        self.assertEqual([i["id"] for i in items],
                         ["note:41", "note:42", "file:88"])
        note_calls = [c for c in v.calls if "/v1/notes" in c["url"]]
        self.assertEqual(note_calls[0]["params"]["start"], 0)
        self.assertEqual(note_calls[1]["params"]["start"], 100)
        self.assertEqual(note_calls[0]["params"]["limit"], 100)

    def test_fetch_note_renders_md_with_context(self):
        item = {"id": "note:41", "name": "Note (Pemberton lease)",
                "kind": "note", "modified": "2026-07-02 09:00:00",
                "meta": self.NOTE}
        name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".md"))
        text = body.decode()
        self.assertIn("Deal: Pemberton lease", text)
        self.assertIn("Person: Ana Diaz", text)
        self.assertIn("Discussed the lease terms.", text)
        self.assertNotIn("<p>", text)
        self.assertEqual(prov["date"], "2026-07-01 10:00:00")
        self.assertEqual(prov["author"], "Jake Anderson")
        self.assertEqual(prov["deal"], "Pemberton lease")

    def test_fetch_file_downloads_bytes(self):
        item = {"id": "file:88", "name": "signed-agreement.pdf",
                "kind": "file", "modified": "2026-06-30 08:00:00",
                "meta": self.FILE}
        with MockVendor([
            ("GET", f"{PD}/v1/files/88/download",
             FakeResponse(content=b"%PDF-1.7 pipedrive")),
        ]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(name, "signed-agreement.pdf")
        self.assertEqual(body, b"%PDF-1.7 pipedrive")
        self.assertTrue(v.calls[0]["url"].endswith("/v1/files/88/download"))
        self.assertEqual(v.calls[0]["headers"]["x-api-token"], "pd-token")
        self.assertEqual(prov["deal"], "Pemberton lease")

    def test_bad_token_maps_to_auth_error(self):
        with MockVendor([("GET", PD, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
