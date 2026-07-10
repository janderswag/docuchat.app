"""Per-adapter proofs for the notes/wiki/work-management batch (v0.3.0, D-81):
Notion, Confluence, Airtable, Coda, ClickUp, monday.com, Asana — each against
its vendor's DOCUMENTED response shapes (2026-07-10 research pass), mocked at
the connectors.request layer via the shared MockVendor harness. No network.
"""

import csv
import io
import json
import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import connectors  # noqa: E402

from tests.test_adapters import (  # noqa: E402
    FakeResponse, MockVendor, fetch_contract_check, service_contract_check)


SLUGS = ("notion", "confluence", "airtable", "coda", "clickup", "monday",
         "asana")


class TestRegistryDiscovery(unittest.TestCase):
    def test_all_seven_register_with_slug_matching_module(self):
        reg = connectors.registry()
        for slug in SLUGS:
            self.assertIn(slug, reg, f"{slug} missing from registry")
            self.assertTrue(reg[slug].__name__.endswith(f".{slug}"),
                            f"SERVICE slug {slug!r} != module filename")


# --------------------------------------------------------------- Notion ----

def _nrt(text):
    return [{"type": "text", "plain_text": text}]


def _nblock(bid, btype, payload, has_children=False):
    return {"object": "block", "id": bid, "type": btype, btype: payload,
            "has_children": has_children}


class TestNotion(unittest.TestCase):
    CREDS = {"token": "ntn_test"}
    NB = "https://api.notion.com/v1"
    PAGE = {
        "object": "page", "id": "page1",
        "created_time": "2026-06-01T00:00:00.000Z",
        "last_edited_time": "2026-07-01T00:00:00.000Z",
        "created_by": {"object": "user", "id": "user-9"},
        "url": "https://www.notion.so/Case-Brief-page1",
        "properties": {"title": {"id": "title", "type": "title",
                                 "title": _nrt("Case Brief")}},
    }

    def _mod(self):
        from connectors import notion
        return notion

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        # the sharing gotcha must be spelled out for the user
        steps = " ".join(self._mod().SERVICE["key_steps"]).lower()
        self.assertIn("connections", steps)

    def test_auth_headers_and_label(self):
        me = FakeResponse(json_data={"object": "user", "name": "docuchat bot",
                                     "type": "bot",
                                     "bot": {"workspace_name": "Firm"}})
        with MockVendor([("GET", f"{self.NB}/users/me", me)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("docuchat bot", label)
        call = v.calls[0]
        self.assertEqual(call["headers"]["Authorization"], "Bearer ntn_test")
        self.assertEqual(call["headers"]["Notion-Version"], "2026-03-11")

    def test_list_paginates_search(self):
        page2 = dict(self.PAGE, id="page2")
        pages = iter([
            FakeResponse(json_data={"results": [self.PAGE],
                                    "has_more": True, "next_cursor": "c2"}),
            FakeResponse(json_data={"results": [page2], "has_more": False}),
        ])
        with MockVendor([("POST", f"{self.NB}/search",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["page1", "page2"])
        self.assertEqual(items[0]["name"], "Case Brief")
        body0 = v.calls[0]["json_body"]
        self.assertEqual(body0["filter"], {"property": "object",
                                           "value": "page"})
        self.assertEqual(v.calls[1]["json_body"]["start_cursor"], "c2")

    def test_fetch_renders_nested_blocks_to_markdown(self):
        top = [
            _nblock("b-h1", "heading_1", {"rich_text": _nrt("Brief")}),
            _nblock("b-p", "paragraph", {"rich_text": _nrt("Intro line.")}),
            _nblock("b-li", "bulleted_list_item",
                    {"rich_text": _nrt("Point one")}, has_children=True),
            _nblock("b-td", "to_do", {"rich_text": _nrt("Done item"),
                                      "checked": True}),
            _nblock("b-q", "quote", {"rich_text": _nrt("Quoted words")}),
            _nblock("b-c", "code", {"rich_text": _nrt("print('hi')"),
                                    "language": "python"}),
            _nblock("b-tbl", "table", {"has_column_header": True},
                    has_children=True),
            _nblock("b-x", "callout", {"rich_text": _nrt("Unknown type text")}),
        ]
        nested = [_nblock("b-li-1", "paragraph",
                          {"rich_text": _nrt("Nested detail.")})]
        rows = [
            _nblock("r1", "table_row",
                    {"cells": [_nrt("Col A"), _nrt("Col B")]}),
            _nblock("r2", "table_row", {"cells": [_nrt("1"), _nrt("2")]}),
        ]
        routes = [
            ("GET", f"{self.NB}/blocks/page1/children",
             FakeResponse(json_data={"results": top, "has_more": False})),
            ("GET", f"{self.NB}/blocks/b-li/children",
             FakeResponse(json_data={"results": nested, "has_more": False})),
            ("GET", f"{self.NB}/blocks/b-tbl/children",
             FakeResponse(json_data={"results": rows, "has_more": False})),
        ]
        item = {"id": "page1", "name": "Case Brief", "kind": "page",
                "modified": "2026-07-01T00:00:00.000Z", "meta": self.PAGE}
        with MockVendor(routes):
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(name, "Case Brief.md")
        text = body.decode()
        self.assertIn("# Brief", text)
        self.assertIn("Intro line.", text)
        self.assertIn("- Point one", text)
        self.assertIn("  Nested detail.", text)     # nested, indented
        self.assertIn("- [x] Done item", text)
        self.assertIn("> Quoted words", text)
        self.assertIn("```python", text)
        self.assertIn("| Col A | Col B |", text)
        self.assertIn("| --- | --- |", text)
        self.assertIn("| 1 | 2 |", text)
        self.assertIn("Unknown type text", text)    # unknown block kept
        self.assertEqual(prov["url"], self.PAGE["url"])
        self.assertEqual(prov["date"], "2026-07-01T00:00:00.000Z")

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", self.NB, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# ----------------------------------------------------------- Confluence ----

class TestConfluence(unittest.TestCase):
    CREDS = {"site": "https://firm.atlassian.net/wiki",
             "email": "jake@firm.example", "api_token": "attok"}
    CB = "https://firm.atlassian.net"

    def _mod(self):
        from connectors import confluence
        return confluence

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        # honest reconnect note for the 365-day token expiry
        self.assertIn("expire", self._mod().SERVICE["plan_note"].lower())

    def test_basic_auth_and_label(self):
        me = FakeResponse(json_data={"accountId": "abc",
                                     "displayName": "Jake A"})
        with MockVendor([("GET", f"{self.CB}/wiki/rest/api/user/current",
                          me)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("Jake A", label)
        self.assertEqual(v.calls[0]["auth"], ("jake@firm.example", "attok"))
        self.assertNotIn("Authorization", v.calls[0]["headers"])

    def test_list_paginates_by_cursor(self):
        pages = iter([
            FakeResponse(json_data={
                "results": [{"id": 111, "title": "Engagement policy",
                             "createdAt": "2026-06-01T00:00:00Z",
                             "version": {"createdAt": "2026-07-02T00:00:00Z",
                                         "number": 3},
                             "_links": {"webui": "/spaces/X/pages/111"}}],
                "_links": {"next": "/wiki/api/v2/pages?cursor=abc123"}}),
            FakeResponse(json_data={
                "results": [{"id": 222, "title": "Runbook",
                             "createdAt": "2026-06-10T00:00:00Z"}],
                "_links": {}}),
        ])
        with MockVendor([("GET", f"{self.CB}/wiki/api/v2/pages",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["111", "222"])
        self.assertEqual(v.calls[1]["params"]["cursor"], "abc123")
        self.assertEqual(items[0]["modified"], "2026-07-02T00:00:00Z")

    def test_fetch_saves_storage_body_as_html(self):
        page = FakeResponse(json_data={
            "id": 111, "title": "Engagement policy",
            "authorId": "acct-1", "createdAt": "2026-06-01T00:00:00Z",
            "version": {"createdAt": "2026-07-02T00:00:00Z", "number": 3},
            "body": {"storage": {"value": "<p>Policy &amp; scope</p>",
                                 "representation": "storage"}},
            "_links": {"webui": "/spaces/X/pages/111"}})
        item = {"id": "111", "name": "Engagement policy", "kind": "page",
                "modified": None, "meta": {}}
        with MockVendor([("GET", f"{self.CB}/wiki/api/v2/pages/111",
                          page)]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        # body-format param is mandatory or Confluence returns an empty body
        self.assertEqual(v.calls[0]["params"]["body-format"], "storage")
        self.assertEqual(name, "Engagement policy.html")
        text = body.decode()
        self.assertIn("<title>Engagement policy</title>", text)
        self.assertIn("<p>Policy &amp; scope</p>", text)
        self.assertEqual(prov["url"],
                         f"{self.CB}/wiki/spaces/X/pages/111")
        self.assertEqual(prov["author"], "acct-1")

    def test_bad_token_maps_to_auth_error(self):
        with MockVendor([("GET", self.CB, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# ------------------------------------------------------------- Airtable ----

class TestAirtable(unittest.TestCase):
    CREDS = {"token": "patTESTTOKEN"}
    AB = "https://api.airtable.com/v0"

    def _mod(self):
        from connectors import airtable
        return airtable

    def test_service_metadata(self):
        service_contract_check(self, self._mod())

    def test_bearer_auth_and_label(self):
        who = FakeResponse(json_data={"id": "usrX",
                                      "scopes": ["data.records:read"]})
        with MockVendor([("GET", f"{self.AB}/meta/whoami", who)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("usrX", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer patTESTTOKEN")

    def test_list_one_item_per_table_with_offset_pagination(self):
        bases = iter([
            FakeResponse(json_data={"bases": [{"id": "app1",
                                               "name": "Matters"}],
                                    "offset": "o2"}),
            FakeResponse(json_data={"bases": [{"id": "app2",
                                               "name": "Clients"}]}),
        ])

        def tables(call):
            base_id = call["url"].split("/")[-2]
            table = ({"id": "tblA", "name": "Deadlines",
                      "fields": [{"name": "Name"}, {"name": "Due"}]}
                     if base_id == "app1" else
                     {"id": "tblB", "name": "Contacts",
                      "fields": [{"name": "Name"}]})
            return FakeResponse(json_data={"tables": [table]})

        routes = [
            # tables route FIRST: its URL shares the /meta/bases prefix
            ("GET", f"{self.AB}/meta/bases/", tables),
            ("GET", f"{self.AB}/meta/bases", lambda call: next(bases)),
        ]
        with MockVendor(routes) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items],
                         ["app1:tblA", "app2:tblB"])
        base_calls = [c for c in v.calls
                      if c["url"].endswith("/meta/bases")]
        self.assertEqual(base_calls[1]["params"].get("offset"), "o2")

    def test_fetch_renders_table_to_csv_with_stable_columns(self):
        pages = iter([
            FakeResponse(json_data={
                "records": [{"id": "rec1",
                             "createdTime": "2026-07-01T00:00:00.000Z",
                             "fields": {"Name": "Acme", "Amount": 100}}],
                "offset": "off2"}),
            FakeResponse(json_data={
                "records": [{"id": "rec2",
                             "createdTime": "2026-07-02T00:00:00.000Z",
                             "fields": {"Name": "Beta",
                                        "Notes": "call, then file",
                                        "Tags": ["a", "b"]}}]}),
        ])
        item = {"id": "app1:tblA", "name": "Matters - Deadlines",
                "kind": "table", "modified": None,
                "meta": {"base_id": "app1", "base_name": "Matters",
                         "table_id": "tblA", "table_name": "Deadlines",
                         "fields": ["Name", "Amount", "Notes"]}}
        with MockVendor([("GET", f"{self.AB}/app1/tblA",
                          lambda call: next(pages))]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(v.calls[1]["params"].get("offset"), "off2")
        self.assertEqual(name, "Matters - Deadlines.csv")
        rows = list(csv.reader(io.StringIO(body.decode())))
        # schema order first, record-only extras appended
        self.assertEqual(rows[0], ["Name", "Amount", "Notes", "Tags"])
        self.assertEqual(rows[1], ["Acme", "100", "", ""])
        self.assertEqual(rows[2], ["Beta", "", "call, then file",
                                   '["a", "b"]'])
        self.assertEqual(prov["date"], "2026-07-02T00:00:00.000Z")

    def test_bad_token_maps_to_auth_error(self):
        with MockVendor([("GET", self.AB, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# ----------------------------------------------------------------- Coda ----

class TestCoda(unittest.TestCase):
    CREDS = {"token": "coda-tok"}
    CB = "https://coda.io/apis/v1"

    def _mod(self):
        from connectors import coda
        return coda

    def setUp(self):
        mod = self._mod()
        self._interval = mod.POLL_INTERVAL
        mod.POLL_INTERVAL = 0
        self.addCleanup(setattr, mod, "POLL_INTERVAL", self._interval)

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        # rebrand honesty: the drawer copy must mention Superhuman Docs
        self.assertIn("Superhuman", self._mod().SERVICE["plan_note"])

    def test_bearer_auth_and_label(self):
        who = FakeResponse(json_data={"name": "Jake",
                                      "loginId": "jake@firm.example"})
        with MockVendor([("GET", f"{self.CB}/whoami", who)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("Jake", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer coda-tok")

    def test_list_paginates_by_page_token(self):
        pages = iter([
            FakeResponse(json_data={"items": [{"id": "doc1",
                                               "name": "Playbook",
                                               "updatedAt": "2026-07-01"}],
                                    "nextPageToken": "t2"}),
            FakeResponse(json_data={"items": [{"id": "doc2",
                                               "name": "Notes"}]}),
        ])
        with MockVendor([("GET", f"{self.CB}/docs",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["doc1", "doc2"])
        self.assertEqual(v.calls[1]["params"].get("pageToken"), "t2")

    def test_fetch_runs_async_export_poll_loop(self):
        statuses = iter([
            FakeResponse(json_data={"status": "inProgress"}),
            FakeResponse(json_data={
                "status": "complete",
                "downloadLink": "https://coda-export.example/dl1"}),
        ])
        routes = [
            # status route FIRST: it shares the /docs/doc1/pages prefix
            ("GET", f"{self.CB}/docs/doc1/pages/canvas-1/export/req1",
             lambda call: next(statuses)),
            ("POST", f"{self.CB}/docs/doc1/pages/canvas-1/export",
             FakeResponse(json_data={"id": "req1", "status": "inProgress"})),
            ("GET", f"{self.CB}/docs/doc1/pages",
             FakeResponse(json_data={"items": [{"id": "canvas-1",
                                                "name": "Overview"}]})),
            ("GET", "https://coda-export.example/dl1",
             FakeResponse(content=b"Overview body text.")),
        ]
        doc = {"id": "doc1", "name": "Playbook",
               "updatedAt": "2026-07-01T00:00:00Z", "ownerName": "Jake",
               "browserLink": "https://coda.io/d/_ddoc1"}
        item = {"id": "doc1", "name": "Playbook", "kind": "doc",
                "modified": doc["updatedAt"], "meta": doc}
        with MockVendor(routes) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        begin = [c for c in v.calls if c["method"] == "POST"]
        self.assertEqual(begin[0]["json_body"], {"outputFormat": "markdown"})
        polls = [c for c in v.calls if "/export/req1" in c["url"]]
        self.assertEqual(len(polls), 2)     # polled until complete
        download = [c for c in v.calls
                    if c["url"].startswith("https://coda-export.example")]
        self.assertNotIn("Authorization", download[0]["headers"])
        self.assertEqual(name, "Playbook.md")
        text = body.decode()
        self.assertIn("# Playbook", text)
        self.assertIn("## Overview", text)
        self.assertIn("Overview body text.", text)
        self.assertEqual(prov["author"], "Jake")

    def test_poll_loop_is_bounded(self):
        routes = [
            ("GET", f"{self.CB}/docs/doc1/pages/canvas-1/export/req1",
             lambda call: FakeResponse(json_data={"status": "inProgress"})),
            ("POST", f"{self.CB}/docs/doc1/pages/canvas-1/export",
             FakeResponse(json_data={"id": "req1", "status": "inProgress"})),
            ("GET", f"{self.CB}/docs/doc1/pages",
             FakeResponse(json_data={"items": [{"id": "canvas-1",
                                                "name": "Overview"}]})),
        ]
        item = {"id": "doc1", "name": "Playbook", "kind": "doc",
                "modified": None, "meta": {"id": "doc1", "name": "Playbook"}}
        with MockVendor(routes) as v:
            with self.assertRaises(connectors.ConnectorUnavailable):
                self._mod().fetch_item(self.CREDS, item)
        polls = [c for c in v.calls if "/export/req1" in c["url"]]
        self.assertEqual(len(polls), self._mod().MAX_POLLS)

    def test_bad_token_maps_to_auth_error(self):
        with MockVendor([("GET", self.CB, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# -------------------------------------------------------------- ClickUp ----

class TestClickUp(unittest.TestCase):
    CREDS = {"token": "pk_123_ABC"}
    V2 = "https://api.clickup.com/api/v2"
    V3 = "https://api.clickup.com/api/v3"

    def _mod(self):
        from connectors import clickup
        return clickup

    def test_service_metadata(self):
        service_contract_check(self, self._mod())

    def test_raw_token_auth_no_bearer(self):
        me = FakeResponse(json_data={"user": {"id": 1, "username": "jake",
                                              "email": "jake@firm.example"}})
        with MockVendor([("GET", f"{self.V2}/user", me)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("jake", label)
        auth = v.calls[0]["headers"]["Authorization"]
        self.assertEqual(auth, "pk_123_ABC")            # documented scheme:
        self.assertFalse(auth.startswith("Bearer"))     # no Bearer prefix

    def test_list_walks_teams_docs_pages_with_cursor(self):
        searches = iter([
            FakeResponse(json_data={"docs": [{"id": "doc1",
                                              "name": "Engagements",
                                              "date_updated": 1783036800000}],
                                    "next_cursor": "nc2"}),
            FakeResponse(json_data={"docs": [], "next_cursor": None}),
        ])
        routes = [
            ("GET", f"{self.V2}/team",
             FakeResponse(json_data={"teams": [{"id": "9001",
                                                "name": "Firm"}]})),
            # pageListing route FIRST: it shares the /docs prefix
            ("GET", f"{self.V3}/workspaces/9001/docs/doc1/pageListing",
             FakeResponse(json_data=[{"id": "pg1", "name": "Root",
                                      "pages": [{"id": "pg2",
                                                 "name": "Child"}]}])),
            ("GET", f"{self.V3}/workspaces/9001/docs",
             lambda call: next(searches)),
        ]
        with MockVendor(routes) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["pg1", "pg2"])
        doc_calls = [c for c in v.calls
                     if c["url"].endswith("/workspaces/9001/docs")]
        self.assertEqual(doc_calls[1]["params"].get("next_cursor"), "nc2")

    def test_fetch_page_as_markdown(self):
        page = FakeResponse(json_data={"id": "pg1", "name": "Root",
                                       "content": "Hello **world**",
                                       "date_updated": 1783036800000})
        item = {"id": "pg1", "name": "Root", "kind": "doc_page",
                "modified": None,
                "meta": {"workspace_id": "9001", "workspace_name": "Firm",
                         "doc_id": "doc1", "doc_name": "Engagements"}}
        with MockVendor([("GET",
                          f"{self.V3}/workspaces/9001/docs/doc1/pages/pg1",
                          page)]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(v.calls[0]["params"]["content_format"], "text/md")
        self.assertEqual(name, "Engagements - Root.md")
        text = body.decode()
        self.assertIn("# Root", text)
        self.assertIn("Hello **world**", text)
        self.assertTrue(prov["date"].startswith("2026-07"))

    def test_bad_token_maps_to_auth_error(self):
        with MockVendor([("GET", self.V2, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# --------------------------------------------------------------- monday ----

class TestMonday(unittest.TestCase):
    CREDS = {"token": "montok123"}
    URL = "https://api.monday.com/v2"

    def _mod(self):
        from connectors import monday
        return monday

    def test_service_metadata(self):
        service_contract_check(self, self._mod())

    def test_graphql_me_query_and_raw_token(self):
        me = FakeResponse(json_data={"data": {"me": {
            "name": "Jake", "email": "jake@firm.example"}}})
        with MockVendor([("POST", self.URL, me)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("Jake", label)
        call = v.calls[0]
        self.assertEqual(call["headers"]["Authorization"], "montok123")
        self.assertFalse(call["headers"]["Authorization"].startswith("Bearer"))
        self.assertIn("API-Version", call["headers"])
        self.assertIn("me { name email }", call["json_body"]["query"])

    def test_list_docs_paginates_at_graphql_root(self):
        mod = self._mod()
        self._page_size = mod.PAGE_SIZE
        mod.PAGE_SIZE = 2
        self.addCleanup(setattr, mod, "PAGE_SIZE", self._page_size)

        def respond(call):
            q = call["json_body"]["query"]
            if "page: 1" in q:
                docs = [{"id": "777", "object_id": "1", "name": "Closing",
                         "workspace_id": 5, "url": "u1",
                         "created_at": "2026-07-01T00:00:00Z"},
                        {"id": "778", "object_id": "2", "name": "Intake",
                         "workspace_id": 5, "url": "u2",
                         "created_at": "2026-07-02T00:00:00Z"}]
            else:
                docs = [{"id": "779", "object_id": "3", "name": "Memo",
                         "workspace_id": 5, "url": "u3",
                         "created_at": "2026-07-03T00:00:00Z"}]
            return FakeResponse(json_data={"data": {"docs": docs}})

        with MockVendor([("POST", self.URL, respond)]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["777", "778", "779"])
        self.assertIn("docs (limit: 2, page: 2)",
                      v.calls[1]["json_body"]["query"])

    def test_fetch_renders_workdoc_blocks(self):
        blocks = [
            {"id": "b1", "type": "large title",
             "content": json.dumps({"deltaFormat": [{"insert": "Overview"}]})},
            {"id": "b2", "type": "normal text",
             "content": json.dumps({"deltaFormat":
                                     [{"insert": "File the motion."}]})},
            {"id": "b3", "type": "bulleted list",
             "content": json.dumps({"deltaFormat":
                                     [{"insert": "Exhibit A"}]})},
        ]
        doc = FakeResponse(json_data={"data": {"docs": [{
            "id": "777", "name": "Closing checklist",
            "url": "https://firm.monday.com/docs/777",
            "created_at": "2026-07-01T00:00:00Z", "blocks": blocks}]}})
        item = {"id": "777", "name": "Closing checklist", "kind": "workdoc",
                "modified": None, "meta": {}}
        with MockVendor([("POST", self.URL, doc)]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        query = v.calls[0]["json_body"]["query"]
        self.assertIn("docs (ids: [777])", query)
        self.assertIn("blocks", query)
        self.assertEqual(name, "Closing checklist.md")
        text = body.decode()
        self.assertIn("# Overview", text)
        self.assertIn("File the motion.", text)
        self.assertIn("- Exhibit A", text)
        self.assertEqual(prov["url"], "https://firm.monday.com/docs/777")

    def test_graphql_level_auth_error(self):
        # monday can answer HTTP 200 with an errors payload on a bad token
        bad = FakeResponse(json_data={"errors":
                                      [{"message": "Not Authenticated"}]})
        with MockVendor([("POST", self.URL, bad)]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)

    def test_bad_token_maps_to_auth_error(self):
        with MockVendor([("POST", self.URL, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# ---------------------------------------------------------------- Asana ----

class TestAsana(unittest.TestCase):
    CREDS = {"token": "asana-pat"}
    AB = "https://app.asana.com/api/1.0"

    def _mod(self):
        from connectors import asana
        return asana

    def test_service_metadata(self):
        service_contract_check(self, self._mod())

    def test_bearer_auth_and_label(self):
        me = FakeResponse(json_data={"data": {"name": "Jake",
                                              "email": "jake@firm.example"}})
        with MockVendor([("GET", f"{self.AB}/users/me", me)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("Jake", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer asana-pat")

    def test_list_filters_to_asana_hosted_attachments(self):
        projects = iter([
            FakeResponse(json_data={"data": [{"gid": "pr1",
                                              "name": "Pemberton"}],
                                    "next_page": {"offset": "of2"}}),
            FakeResponse(json_data={"data": [{"gid": "pr2", "name": "Acme"}],
                                    "next_page": None}),
        ])

        def attachments(call):
            if call["params"].get("parent") == "pr1":
                return FakeResponse(json_data={"data": [
                    {"gid": "att1", "name": "engagement.pdf",
                     "host": "asana",
                     "download_url": "https://asana-files.example/sig1",
                     "created_at": "2026-07-01T00:00:00Z"},
                    {"gid": "att2", "name": "shared drive doc",
                     "host": "gdrive", "download_url": None,
                     "created_at": "2026-07-01T00:00:00Z"},
                ]})
            return FakeResponse(json_data={"data": []})

        routes = [
            ("GET", f"{self.AB}/workspaces",
             FakeResponse(json_data={"data": [{"gid": "ws1",
                                               "name": "Firm"}]})),
            ("GET", f"{self.AB}/projects", lambda call: next(projects)),
            ("GET", f"{self.AB}/attachments", attachments),
        ]
        with MockVendor(routes) as v:
            items = self._mod().list_items(self.CREDS)
        # externally hosted attachment (null download_url) filtered out
        self.assertEqual([i["id"] for i in items], ["att1"])
        project_calls = [c for c in v.calls if "/projects" in c["url"]]
        self.assertEqual(project_calls[1]["params"].get("offset"), "of2")
        att_call = [c for c in v.calls if "/attachments" in c["url"]][0]
        for field in ("host", "download_url", "created_at"):
            self.assertIn(field, att_call["params"]["opt_fields"])

    def test_fetch_rerequests_and_downloads_immediately(self):
        att = FakeResponse(json_data={"data": {
            "gid": "att1", "name": "engagement.pdf", "host": "asana",
            "download_url": "https://asana-files.example/sig1",
            "permanent_url": "https://app.asana.com/app/asana/-/att1",
            "created_at": "2026-07-01T00:00:00Z",
            "parent": {"gid": "task9", "name": "Sign engagement"}}})
        routes = [
            ("GET", f"{self.AB}/attachments/att1", att),
            ("GET", "https://asana-files.example/sig1",
             FakeResponse(content=b"%PDF-1.4 fake bytes")),
        ]
        item = {"id": "att1", "name": "engagement.pdf", "kind": "attachment",
                "modified": "2026-07-01T00:00:00Z",
                "meta": {"workspace_name": "Firm",
                         "project_name": "Pemberton", "attachment": {}}}
        with MockVendor(routes) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(name, "engagement.pdf")    # real extension kept
        self.assertEqual(body, b"%PDF-1.4 fake bytes")
        # the ~2-minute URL is re-requested, then fetched with no auth header
        self.assertIn("/attachments/att1", v.calls[0]["url"])
        download = [c for c in v.calls
                    if c["url"].startswith("https://asana-files.example")][0]
        self.assertNotIn("Authorization", download["headers"])
        self.assertEqual(prov["parent"], "Sign engagement")
        self.assertEqual(prov["date"], "2026-07-01T00:00:00Z")

    def test_fetch_external_host_raises_access_error(self):
        att = FakeResponse(json_data={"data": {
            "gid": "att2", "name": "shared drive doc", "host": "gdrive",
            "download_url": None}})
        item = {"id": "att2", "name": "shared drive doc",
                "kind": "attachment", "modified": None,
                "meta": {"project_name": "Pemberton"}}
        with MockVendor([("GET", f"{self.AB}/attachments/att2", att)]):
            with self.assertRaises(connectors.ConnectorAccessError):
                self._mod().fetch_item(self.CREDS, item)

    def test_bad_token_maps_to_auth_error(self):
        with MockVendor([("GET", self.AB, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
