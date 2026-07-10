"""Per-adapter proofs (v0.3.0, D-81) — Grain, Jiminny, Rev AI, Sonix, Trint,
and Happy Scribe against their vendors' DOCUMENTED response shapes (from the
2026-07-10 research pass: research_notetakers2.json, research_transcription
.json), mocked at the connectors.request layer via the shared harness in
tests.test_adapters. No network. Each adapter suite proves service metadata,
exact documented auth, full pagination (including Jiminny's <6-month date
windows and Happy Scribe's bounded export poll), fetch rendering to an
ingestible file with provenance, and 401 -> ConnectorAuthError.
"""

import datetime
import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import connectors  # noqa: E402

from tests.test_adapters import (  # noqa: E402
    FakeResponse, MockVendor, fetch_contract_check, service_contract_check)


# --- Grain ----------------------------------------------------------------------

GRAIN_BASE = "https://api.grain.com/_/public-api/v2"


class TestGrain(unittest.TestCase):
    CREDS = {"api_key": "grain-pat"}
    REC = {
        "id": "rec-1", "title": "Deposition prep",
        "start_datetime": "2026-06-01T15:00:00Z",
        "end_datetime": "2026-06-01T16:00:00Z", "duration_ms": 3600000,
        "owner": "ana@firm.example",
        "url": "https://grain.com/share/recording/rec-1",
        "participants": [{"name": "Ana"}, {"name": "Jake"}],
    }

    def _mod(self):
        from connectors import grain
        return grain

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        self.assertEqual(self._mod().SERVICE["slug"], "grain")
        self.assertIn("Business", self._mod().SERVICE["plan_note"])

    def test_auth_bearer_plus_version_header(self):
        page = FakeResponse(json_data={"recordings": [self.REC], "cursor": None})
        with MockVendor([("POST", f"{GRAIN_BASE}/recordings", page)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("recordings", label)
        h = v.calls[0]["headers"]
        self.assertEqual(h["Authorization"], "Bearer grain-pat")
        # documented gotcha: this header is REQUIRED on every call
        self.assertEqual(h["Public-Api-Version"], "2025-10-31")

    def test_list_posts_and_paginates_by_cursor(self):
        pages = iter([
            FakeResponse(json_data={"recordings": [self.REC], "cursor": "c2"}),
            FakeResponse(json_data={"recordings": [dict(self.REC, id="rec-2")],
                                    "cursor": None}),
        ])
        with MockVendor([("POST", f"{GRAIN_BASE}/recordings",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["rec-1", "rec-2"])
        # documented gotcha: list is POST with the cursor in the JSON body
        self.assertEqual(v.calls[0]["method"], "POST")
        self.assertEqual(v.calls[1]["json_body"]["cursor"], "c2")

    def test_fetch_downloads_vtt_with_provenance(self):
        vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n<v Ana>Hello.\n"
        route = ("GET", f"{GRAIN_BASE}/recordings/rec-1/transcript.vtt",
                 FakeResponse(content=vtt))
        item = {"id": "rec-1", "name": "Deposition prep", "kind": "transcript",
                "modified": "2026-06-01T16:00:00Z", "meta": self.REC}
        with MockVendor([route]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        self.assertEqual(body, vtt)
        self.assertEqual(prov["speakers"], ["Ana", "Jake"])
        self.assertEqual(prov["url"], "https://grain.com/share/recording/rec-1")
        self.assertEqual(v.calls[0]["headers"]["Public-Api-Version"], "2025-10-31")

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("POST", "https://api.grain.com", FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# --- Jiminny --------------------------------------------------------------------

JIMINNY_US = "https://app.jiminny.com/customer/api/v1"
JIMINNY_EU = "https://app.jiminny.eu/customer/api/v1"


class TestJiminny(unittest.TestCase):
    CREDS = {"api_key": "jm-key", "region": "us"}
    ACT = {
        "id": "a-1", "type": "conference", "title": "Discovery call",
        "createdAt": "2026-06-20T10:00:00Z",
        "actualStartTime": "2026-06-20T10:01:00Z",
        "updatedAt": "2026-06-20T11:00:00Z", "status": "completed",
        "participants": [{"id": "p1", "name": "Jake"},
                         {"id": "p2", "name": "Ana"}],
        "organizer": {"name": "Jake", "email": "jake@firm.example"},
        "crmUrl": "https://crm.example/deal/9",
    }

    def _mod(self):
        from connectors import jiminny
        return jiminny

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        self.assertEqual(self._mod().SERVICE["slug"], "jiminny")
        # the Admin/Owner gate must be said out loud in the key steps
        self.assertTrue(any("Admin" in s for s in
                            self._mod().SERVICE["key_steps"]))
        self.assertTrue(any(f["key"] == "region" for f in
                            self._mod().SERVICE["fields"]))

    def test_auth_bearer_and_region_base_url(self):
        org = FakeResponse(json_data={"name": "Anderson Law"})
        with MockVendor([("GET", f"{JIMINNY_EU}/me", org)]) as v:
            label = self._mod().test({"api_key": "jm-key", "region": "eu"})
        self.assertIn("Anderson Law", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"], "Bearer jm-key")
        self.assertTrue(v.calls[0]["url"].startswith("https://app.jiminny.eu/"))

    def test_list_windows_backwards_and_pages_within_window(self):
        windows = []  # (fromDate, toDate) in call order

        def route(call):
            p = call["params"]
            key = (p["fromDate"], p["toDate"])
            if key not in windows:
                windows.append(key)
            if key == windows[0] and p["page"] == 1:
                return FakeResponse(json_data={
                    "results": [self.ACT],
                    "metadata": {"page": 1, "pageSize": 500, "maxPage": 2,
                                 "nextPage": "https://next"}})
            if key == windows[0] and p["page"] == 2:
                return FakeResponse(json_data={
                    "results": [dict(self.ACT, id="a-2")],
                    "metadata": {"page": 2, "pageSize": 500, "maxPage": 2,
                                 "nextPage": None}})
            return FakeResponse(json_data={"results": [],
                                           "metadata": {"nextPage": None}})

        with MockVendor([("GET", f"{JIMINNY_US}/getActivities", route)]):
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["a-1", "a-2"])
        today = datetime.date.today()
        # every window is under the documented 6-month ceiling
        for frm, to in windows:
            span = (datetime.date.fromisoformat(to)
                    - datetime.date.fromisoformat(frm)).days
            self.assertLessEqual(span, 150)
            self.assertGreater(span, 0)
        # windows walk backwards contiguously from today...
        self.assertEqual(windows[0][1], today.isoformat())
        for (frm, _), (_, next_to) in zip(windows, windows[1:]):
            self.assertEqual(frm, next_to)
        # ...and cover the last three years
        earliest = datetime.date.fromisoformat(windows[-1][0])
        self.assertLessEqual(earliest, today - datetime.timedelta(days=1094))

    def test_list_since_narrows_the_window_walk(self):
        since = (datetime.date.today()
                 - datetime.timedelta(days=30)).isoformat()
        windows = []

        def route(call):
            windows.append((call["params"]["fromDate"],
                            call["params"]["toDate"]))
            return FakeResponse(json_data={"results": [],
                                           "metadata": {"nextPage": None}})

        with MockVendor([("GET", f"{JIMINNY_US}/getActivities", route)]):
            items = self._mod().list_items(self.CREDS, since=since)
        self.assertEqual(items, [])
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0][0], since)

    def test_fetch_renders_segments_to_vtt_with_speakers(self):
        segs = FakeResponse(json_data=[
            {"startsAt": 0.0, "endsAt": 4.5, "transcript": "Good morning.",
             "participantId": "p1"},
            {"startsAt": 5.0, "endsAt": 9.0, "transcript": "Morning.",
             "participantId": "p2"},
        ])
        item = {"id": "a-1", "name": "Discovery call", "kind": "transcript",
                "modified": "2026-06-20T11:00:00Z", "meta": self.ACT}
        with MockVendor([("GET", f"{JIMINNY_US}/getTranscription", segs)]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        text = body.decode()
        self.assertIn("WEBVTT", text)
        self.assertIn("<v Jake>Good morning.", text)
        self.assertIn("00:00:05.000 --> 00:00:09.000", text)
        self.assertEqual(prov["speakers"], ["Ana", "Jake"])
        self.assertEqual(prov["author"], "Jake")
        self.assertEqual(v.calls[0]["params"]["activityId"], "a-1")

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", "https://app.jiminny.com", FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# --- Rev AI ---------------------------------------------------------------------

REVAI_BASE = "https://api.rev.ai/speechtotext/v1"


class TestRevAI(unittest.TestCase):
    CREDS = {"api_key": "rv-token"}
    JOB = {
        "id": "job-1", "status": "transcribed", "name": "hearing.mp3",
        "created_on": "2026-07-01T09:00:00Z",
        "completed_on": "2026-07-01T09:05:00Z",
        "duration_seconds": 1800, "language": "en", "type": "async",
    }

    def _mod(self):
        from connectors import revai
        return revai

    def test_service_metadata_is_honest_about_30_days(self):
        service_contract_check(self, self._mod())
        svc = self._mod().SERVICE
        self.assertEqual(svc["slug"], "revai")
        self.assertIn("30 days", svc["blurb"] + " " + svc["plan_note"])

    def test_auth_bearer_and_account_label(self):
        acct = FakeResponse(json_data={"email": "jake@firm.example",
                                       "balance_seconds": 3600})
        with MockVendor([("GET", f"{REVAI_BASE}/account", acct)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("jake@firm.example", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer rv-token")

    def test_list_paginates_with_starting_after_and_filters_unfinished(self):
        first = [dict(self.JOB, id=f"job-{i}") for i in range(100)]
        second = [dict(self.JOB, id="job-x"),
                  dict(self.JOB, id="job-y", status="in_progress")]
        pages = iter([FakeResponse(json_data=first),
                      FakeResponse(json_data=second)])
        with MockVendor([("GET", f"{REVAI_BASE}/jobs",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual(len(items), 101)  # in_progress job excluded
        self.assertEqual(v.calls[1]["params"]["starting_after"], "job-99")
        self.assertNotIn("job-y", [i["id"] for i in items])

    def test_fetch_downloads_vtt_captions(self):
        vtt = b"WEBVTT\n\n1\n00:00:00.000 --> 00:00:04.000\nSpeaker 0: Hi.\n"
        route = ("GET", f"{REVAI_BASE}/jobs/job-1/captions",
                 FakeResponse(content=vtt))
        item = {"id": "job-1", "name": "hearing.mp3", "kind": "transcript",
                "modified": "2026-07-01T09:05:00Z", "meta": self.JOB}
        with MockVendor([route]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        self.assertEqual(body, vtt)
        # documented content negotiation: vtt comes via the Accept header
        self.assertEqual(v.calls[0]["headers"]["Accept"], "text/vtt")
        self.assertEqual(prov["date"], "2026-07-01T09:00:00Z")

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", "https://api.rev.ai", FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# --- Sonix ----------------------------------------------------------------------

SONIX_BASE = "https://api.sonix.ai/v1"


class TestSonix(unittest.TestCase):
    CREDS = {"api_key": "sx-key"}
    MEDIA = {
        "id": "m-1", "name": "Arbitration hearing", "created_at": 1751376000,
        "duration": 3600.5, "status": "completed", "video": False,
    }

    def _mod(self):
        from connectors import sonix
        return sonix

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        svc = self._mod().SERVICE
        self.assertEqual(svc["slug"], "sonix")
        self.assertIn("paid Sonix subscription", svc["plan_note"])

    def test_auth_bearer_and_label(self):
        page = FakeResponse(json_data={"media": [self.MEDIA],
                                       "total_pages": 1, "page": 1})
        with MockVendor([("GET", f"{SONIX_BASE}/media", page)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("transcripts", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer sx-key")

    def test_list_walks_total_pages_and_skips_incomplete(self):
        pages = iter([
            FakeResponse(json_data={
                "media": [self.MEDIA,
                          dict(self.MEDIA, id="m-2", status="transcribing")],
                "total_pages": 2, "page": 1}),
            FakeResponse(json_data={"media": [dict(self.MEDIA, id="m-3")],
                                    "total_pages": 2, "page": 2}),
        ])
        with MockVendor([("GET", f"{SONIX_BASE}/media",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual([i["id"] for i in items], ["m-1", "m-3"])
        self.assertEqual(v.calls[0]["params"]["page"], 1)
        self.assertEqual(v.calls[1]["params"]["page"], 2)
        # epoch created_at is normalised to ISO for the hub
        self.assertTrue(items[0]["modified"].startswith("2025-07-01"))

    def test_fetch_downloads_vtt(self):
        vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:03.000\n<v Speaker 1>Hi.\n"
        route = ("GET", f"{SONIX_BASE}/media/m-1/transcript.vtt",
                 FakeResponse(content=vtt))
        item = {"id": "m-1", "name": "Arbitration hearing",
                "kind": "transcript", "modified": "2025-07-01T00:00:00Z",
                "meta": self.MEDIA}
        with MockVendor([route]):
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        self.assertEqual(body, vtt)
        self.assertIn("Arbitration hearing", name)

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", "https://api.sonix.ai", FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# --- Trint ----------------------------------------------------------------------

TRINT_BASE = "https://api.trint.com"


class TestTrint(unittest.TestCase):
    CREDS = {"key_id": "tk-id", "key_secret": "tk-secret"}
    ROW = {"id": "t-1", "title": "Client interview",
           "createdAt": "2026-06-15T12:00:00Z"}

    def _mod(self):
        from connectors import trint
        return trint

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        svc = self._mod().SERVICE
        self.assertEqual(svc["slug"], "trint")
        self.assertEqual({f["key"] for f in svc["fields"]},
                         {"key_id", "key_secret"})

    def test_auth_is_http_basic_pair_not_header(self):
        page = FakeResponse(json_data=[self.ROW])
        with MockVendor([("GET", f"{TRINT_BASE}/transcripts/", page)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("connected", label)
        # modern keys: Basic auth via the framework's auth= parameter,
        # never the legacy 'api-key' header and no Authorization header
        self.assertEqual(v.calls[0]["auth"], ("tk-id", "tk-secret"))
        self.assertNotIn("Authorization", v.calls[0]["headers"] or {})
        self.assertNotIn("api-key", v.calls[0]["headers"] or {})

    def test_list_paginates_with_skip_and_limit(self):
        first = [dict(self.ROW, id=f"t-{i}") for i in range(100)]
        pages = iter([FakeResponse(json_data=first),
                      FakeResponse(json_data=[dict(self.ROW, id="t-last")])])
        with MockVendor([("GET", f"{TRINT_BASE}/transcripts/",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual(len(items), 101)
        self.assertEqual(v.calls[0]["params"]["skip"], 0)
        self.assertEqual(v.calls[1]["params"]["skip"], 100)
        self.assertEqual(v.calls[1]["params"]["limit"], 100)

    def test_fetch_exports_webvtt_with_basic_auth(self):
        vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n<v Ana>Hello.\n"
        route = ("GET", f"{TRINT_BASE}/export/webvtt/t-1",
                 FakeResponse(content=vtt))
        item = {"id": "t-1", "name": "Client interview", "kind": "transcript",
                "modified": "2026-06-15T12:00:00Z", "meta": self.ROW}
        with MockVendor([route]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        self.assertEqual(body, vtt)
        self.assertEqual(v.calls[0]["auth"], ("tk-id", "tk-secret"))
        self.assertEqual(v.calls[0]["params"]["enable-speakers"], "true")

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", "https://api.trint.com", FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


# --- Happy Scribe ---------------------------------------------------------------

HS_BASE = "https://www.happyscribe.com/api/v1"


class TestHappyScribe(unittest.TestCase):
    CREDS = {"api_key": "hs-key"}
    ORGS = FakeResponse(json_data=[{"id": 7, "name": "Anderson Law"}])
    ROW = {"id": "hs-1", "name": "Deposition audio",
           "createdAt": "2026-06-10T09:00:00Z", "state": "automatic_done",
           "language": "en", "audioLengthInSeconds": 900}

    def _mod(self):
        from connectors import happyscribe
        return happyscribe

    def test_service_metadata(self):
        service_contract_check(self, self._mod())
        self.assertEqual(self._mod().SERVICE["slug"], "happyscribe")

    def test_auth_bearer_and_org_label(self):
        with MockVendor([("GET", f"{HS_BASE}/organizations", self.ORGS)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("Anderson Law", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer hs-key")

    def test_list_resolves_org_id_and_paginates(self):
        first = [dict(self.ROW, id=f"hs-{i}") for i in range(100)]
        pages = iter([FakeResponse(json_data=first),
                      FakeResponse(json_data=[dict(self.ROW, id="hs-last")])])
        routes = [
            ("GET", f"{HS_BASE}/organizations", self.ORGS),
            ("GET", f"{HS_BASE}/transcriptions", lambda call: next(pages)),
        ]
        with MockVendor(routes) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual(len(items), 101)
        list_calls = [c for c in v.calls if "/transcriptions" in c["url"]]
        # organization_id resolved via /organizations, never asked of the user
        self.assertEqual(list_calls[0]["params"]["organization_id"], "7")
        self.assertEqual([c["params"]["page"] for c in list_calls], [0, 1])
        self.assertEqual(list_calls[0]["params"]["per_page"], 100)

    def test_fetch_polls_export_until_ready_then_downloads(self):
        vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n<v Ana>Hi.\n"
        poll = iter([
            FakeResponse(json_data={"id": "ex-1", "state": "processing"}),
            FakeResponse(json_data={"id": "ex-1", "state": "ready",
                                    "download_link":
                                    "https://cdn.happyscribe.example/ex-1.vtt"}),
        ])
        routes = [
            ("POST", f"{HS_BASE}/exports",
             FakeResponse(json_data={"id": "ex-1", "state": "pending"})),
            ("GET", f"{HS_BASE}/exports/ex-1", lambda call: next(poll)),
            ("GET", "https://cdn.happyscribe.example/ex-1.vtt",
             FakeResponse(content=vtt)),
        ]
        item = {"id": "hs-1", "name": "Deposition audio", "kind": "transcript",
                "modified": "2026-06-10T09:00:00Z", "meta": self.ROW}
        mod = self._mod()
        old = mod.POLL_INTERVAL
        mod.POLL_INTERVAL = 0
        try:
            with MockVendor(routes) as v:
                name, body, prov = mod.fetch_item(self.CREDS, item)
        finally:
            mod.POLL_INTERVAL = old
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        self.assertEqual(body, vtt)
        # POST created the export with the documented body...
        self.assertEqual(v.calls[0]["json_body"],
                         {"format": "vtt", "transcription_ids": ["hs-1"]})
        # ...and the poll ran twice before the download
        poll_calls = [c for c in v.calls if "/exports/ex-1" in c["url"]]
        self.assertEqual(len(poll_calls), 2)

    def test_fetch_times_out_honestly_when_export_never_readies(self):
        stuck = FakeResponse(json_data={"id": "ex-1", "state": "processing"})
        routes = [
            ("POST", f"{HS_BASE}/exports",
             FakeResponse(json_data={"id": "ex-1", "state": "pending"})),
            ("GET", f"{HS_BASE}/exports/ex-1", stuck),
        ]
        item = {"id": "hs-1", "name": "Deposition audio", "kind": "transcript",
                "modified": "2026-06-10T09:00:00Z", "meta": self.ROW}
        mod = self._mod()
        old_i, old_a = mod.POLL_INTERVAL, mod.POLL_ATTEMPTS
        mod.POLL_INTERVAL, mod.POLL_ATTEMPTS = 0, 3
        try:
            with MockVendor(routes):
                with self.assertRaises(connectors.ConnectorUnavailable):
                    mod.fetch_item(self.CREDS, item)
        finally:
            mod.POLL_INTERVAL, mod.POLL_ATTEMPTS = old_i, old_a

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", "https://www.happyscribe.com",
                          FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
