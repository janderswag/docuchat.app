"""Meeting-platform adapter proofs (v0.3.0, D-81) — Zoom and Cisco Webex
against their DOCUMENTED response shapes (research_meetings.json, 2026-07-10),
mocked at the connectors.request layer via the shared harness in
test_adapters.py. No network.

Zoom proves the Server-to-Server OAuth token mint (Basic auth + grant_type
params, one mint per operation, Bearer on every subsequent call), the 30-day
from/to month-window walk over 24 months, next_page_token pagination,
TRANSCRIPT-only filtering, VTT download, and 401 -> ConnectorAuthError.
Webex proves personal-token Bearer auth, the windowed recordings+transcripts
listing with Link rel="next" pagination, transcript VTT download, and
401 -> ConnectorAuthError.
"""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import connectors  # noqa: E402
from tests.test_adapters import (FakeResponse, MockVendor,  # noqa: E402
                                 fetch_contract_check, service_contract_check)


class LinkedResponse(FakeResponse):
    """FakeResponse plus response headers (Webex Link-header pagination)."""

    def __init__(self, headers=None, **kw):
        super().__init__(**kw)
        self.headers = headers or {}


class TestZoom(unittest.TestCase):
    CREDS = {"account_id": "acct_9", "client_id": "cid_1", "client_secret": "cs_1"}
    TOKEN = FakeResponse(json_data={"access_token": "zt-abc",
                                    "token_type": "bearer", "expires_in": 3600})
    MEETING = {
        "id": 123456, "uuid": "uu==1", "topic": "Pemberton status call",
        "start_time": "2026-07-01T16:00:00Z",
        "host_email": "jake@firm.example",
        "share_url": "https://zoom.us/rec/share/x",
        "recording_files": [
            {"id": "file_vid", "file_type": "MP4", "file_extension": "MP4",
             "download_url": "https://zoom.us/rec/download/vid"},
            {"id": "file_tr", "file_type": "TRANSCRIPT", "file_extension": "VTT",
             "download_url": "https://zoom.us/rec/download/tr"},
        ],
    }

    def _mod(self):
        from connectors import zoom
        return zoom

    def test_service_metadata(self):
        mod = self._mod()
        service_contract_check(self, mod)
        self.assertEqual(mod.SERVICE["slug"], "zoom")
        self.assertEqual([f["key"] for f in mod.SERVICE["fields"]],
                         ["account_id", "client_id", "client_secret"])
        self.assertIn("Pro or higher", mod.SERVICE["plan_note"])
        steps = " ".join(mod.SERVICE["key_steps"])
        self.assertIn("Server-to-Server OAuth", steps)
        self.assertIn("cloud_recording:read:list_user_recordings:admin", steps)
        self.assertIn("user:read:user:admin", steps)

    def test_token_mint_then_bearer_whoami(self):
        me = FakeResponse(json_data={"id": "u1", "email": "jake@firm.example"})
        with MockVendor([
            ("POST", "https://zoom.us/oauth/token", self.TOKEN),
            ("GET", "https://api.zoom.us/v2/users/me", me),
        ]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("jake@firm.example", label)
        mint = v.calls[0]
        self.assertEqual(mint["method"], "POST")
        self.assertEqual(mint["auth"], ("cid_1", "cs_1"))  # HTTP Basic
        self.assertEqual(mint["params"]["grant_type"], "account_credentials")
        self.assertEqual(mint["params"]["account_id"], "acct_9")
        whoami = v.calls[1]
        self.assertEqual(whoami["headers"]["Authorization"], "Bearer zt-abc")
        self.assertIsNone(whoami["auth"])

    def test_list_walks_month_windows_and_paginates(self):
        state = {"first_window": None}
        m2 = dict(self.MEETING, id=222, topic="Older call",
                  start_time="2026-06-28T10:00:00Z",
                  recording_files=[{"id": "file_tr2", "file_type": "TRANSCRIPT",
                                    "file_extension": "VTT",
                                    "download_url": "https://zoom.us/rec/download/tr2"}])

        def recordings(call):
            p = call["params"]
            if p.get("next_page_token") == "npt-2":
                return FakeResponse(json_data={"meetings": [m2],
                                               "next_page_token": ""})
            if state["first_window"] is None:
                state["first_window"] = (p["from"], p["to"])
            if (p["from"], p["to"]) == state["first_window"]:
                return FakeResponse(json_data={"meetings": [self.MEETING],
                                               "next_page_token": "npt-2"})
            return FakeResponse(json_data={"meetings": [], "next_page_token": ""})

        with MockVendor([
            ("POST", "https://zoom.us/oauth/token", self.TOKEN),
            ("GET", "https://api.zoom.us/v2/users/me/recordings", recordings),
        ]) as v:
            items = self._mod().list_items(self.CREDS)

        mints = [c for c in v.calls if c["url"].startswith("https://zoom.us/oauth")]
        self.assertEqual(len(mints), 1)  # one mint per operation, reused
        rec_calls = [c for c in v.calls
                     if c["url"].endswith("/users/me/recordings")]
        for c in rec_calls:
            self.assertEqual(c["headers"]["Authorization"], "Bearer zt-abc")

        # 24 backward-walking windows, each <= 30 days, contiguous
        windows = []
        for c in rec_calls:
            w = (c["params"]["from"], c["params"]["to"])
            if w not in windows:
                windows.append(w)
        self.assertEqual(len(windows), 24)
        self.assertEqual(windows[0][1], date.today().isoformat())
        for frm, to in windows:
            span = date.fromisoformat(to) - date.fromisoformat(frm)
            self.assertEqual(span.days, 29)  # 30 days inclusive, Zoom's max
        for (frm, _), (_, nxt_to) in zip(windows, windows[1:]):
            self.assertEqual(date.fromisoformat(nxt_to),
                             date.fromisoformat(frm) - timedelta(days=1))

        # pagination reused the same window with the vendor token
        paged = [c for c in rec_calls if c["params"].get("next_page_token")]
        self.assertEqual(len(paged), 1)
        self.assertEqual((paged[0]["params"]["from"], paged[0]["params"]["to"]),
                         state["first_window"])

        # transcript files only — the MP4 never becomes an item
        self.assertEqual([i["id"] for i in items], ["file_tr", "file_tr2"])
        self.assertTrue(all(i["kind"] == "transcript" for i in items))
        self.assertEqual(items[0]["name"], "Pemberton status call")
        self.assertEqual(items[0]["modified"], "2026-07-01T16:00:00Z")
        self.assertEqual(items[0]["meta"]["host_email"], "jake@firm.example")

    def test_fetch_downloads_vtt_with_bearer(self):
        vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n<v Jake>Hello.\n"
        item = {"id": "file_tr", "name": "Pemberton status call",
                "kind": "transcript", "modified": "2026-07-01T16:00:00Z",
                "meta": {"topic": "Pemberton status call",
                         "start_time": "2026-07-01T16:00:00Z",
                         "host_email": "jake@firm.example",
                         "meeting_id": 123456,
                         "share_url": "https://zoom.us/rec/share/x",
                         "download_url": "https://zoom.us/rec/download/tr",
                         "file_extension": "VTT"}}
        with MockVendor([
            ("POST", "https://zoom.us/oauth/token", self.TOKEN),
            ("GET", "https://zoom.us/rec/download/tr", FakeResponse(content=vtt)),
        ]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(name, "Pemberton status call (2026-07-01).vtt")
        self.assertEqual(body, vtt)
        dl = v.calls[-1]
        self.assertEqual(dl["url"], "https://zoom.us/rec/download/tr")
        self.assertEqual(dl["headers"]["Authorization"], "Bearer zt-abc")
        self.assertEqual(prov["author"], "jake@firm.example")
        self.assertEqual(prov["date"], "2026-07-01T16:00:00Z")
        self.assertEqual(prov["url"], "https://zoom.us/rec/share/x")

    def test_bad_credentials_map_to_auth_error(self):
        with MockVendor([("POST", "https://zoom.us/oauth/token",
                          FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)

    def test_token_response_without_token_is_auth_error(self):
        with MockVendor([("POST", "https://zoom.us/oauth/token",
                          FakeResponse(json_data={"reason": "app not activated"}))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


class TestWebex(unittest.TestCase):
    CREDS = {"access_token": "wx-tok"}
    RECORDING = {"id": "rc1", "meetingId": "mtg1", "topic": "Deposition prep",
                 "createTime": "2026-07-02T15:00:00Z",
                 "hostEmail": "jake@firm.example",
                 "playbackUrl": "https://web.webex.com/play/x", "format": "MP4"}
    TR1 = {"id": "tr1", "meetingId": "mtg1", "meetingTopic": "Deposition prep",
           "startTime": "2026-07-02T15:00:00Z", "hostEmail": "jake@firm.example"}
    TR2 = {"id": "tr2", "meetingId": "mtg2", "meetingTopic": "Client intake",
           "startTime": "2026-07-01T10:00:00Z", "hostEmail": "jake@firm.example"}

    def _mod(self):
        from connectors import webex
        return webex

    def test_service_metadata(self):
        mod = self._mod()
        service_contract_check(self, mod)
        self.assertEqual(mod.SERVICE["slug"], "webex")
        self.assertEqual([f["key"] for f in mod.SERVICE["fields"]],
                         ["access_token"])
        # honest about the 12-hour token: one-time import, reconnect to sync
        self.assertIn("12 hours", mod.SERVICE["plan_note"])
        self.assertIn("one-time import", mod.SERVICE["plan_note"])

    def test_bearer_auth_and_label(self):
        me = FakeResponse(json_data={"displayName": "Jake Anderson",
                                     "emails": ["jake@firm.example"]})
        with MockVendor([("GET", "https://webexapis.com/v1/people/me", me)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("Jake Anderson", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"], "Bearer wx-tok")

    def test_list_windows_link_pagination_and_join(self):
        state = {"first_window": None}
        next_url = "https://webexapis.com/v1/meetingTranscripts?cursor=abc"

        def recordings(call):
            # list_items hits recordings first per window; newest window first
            if state["first_window"] is None:
                state["first_window"] = call["params"]["from"]
            items = [self.RECORDING] \
                if call["params"]["from"] == state["first_window"] else []
            return FakeResponse(json_data={"items": items})

        def transcripts(call):
            if "cursor=abc" in call["url"]:
                return FakeResponse(json_data={"items": [self.TR2]})
            if call["params"]["from"] == state["first_window"]:
                return LinkedResponse(
                    json_data={"items": [self.TR1]},
                    headers={"Link": f'<{next_url}>; rel="next"'})
            return FakeResponse(json_data={"items": []})

        with MockVendor([
            ("GET", "https://webexapis.com/v1/recordings", recordings),
            ("GET", "https://webexapis.com/v1/meetingTranscripts", transcripts),
        ]) as v:
            items = self._mod().list_items(self.CREDS)

        for c in v.calls:
            self.assertEqual(c["headers"]["Authorization"], "Bearer wx-tok")

        # 24 backward-walking 30-day windows on the recordings list
        rec_calls = [c for c in v.calls
                     if c["url"].startswith("https://webexapis.com/v1/recordings")]
        windows = []
        for c in rec_calls:
            w = (c["params"]["from"], c["params"]["to"])
            if w not in windows:
                windows.append(w)
        self.assertEqual(len(windows), 24)
        for frm, to in windows:
            span = date.fromisoformat(to[:10]) - date.fromisoformat(frm[:10])
            self.assertEqual(span.days, 29)

        # Link rel="next" was followed exactly once, with the vendor's URL
        cursor_calls = [c for c in v.calls if "cursor=abc" in c["url"]]
        self.assertEqual(len(cursor_calls), 1)

        # transcripts are the items; recording join fills createTime/playback
        self.assertEqual([i["id"] for i in items], ["tr1", "tr2"])
        self.assertTrue(all(i["kind"] == "transcript" for i in items))
        self.assertEqual(items[0]["name"], "Deposition prep")
        self.assertEqual(items[0]["meta"]["createTime"], "2026-07-02T15:00:00Z")
        self.assertEqual(items[0]["meta"]["playbackUrl"],
                         "https://web.webex.com/play/x")
        self.assertIsNone(items[1]["meta"]["createTime"])  # no recording row

    def test_fetch_downloads_vtt(self):
        vtt = b"WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nJake: Good morning.\n"
        item = {"id": "tr1", "name": "Deposition prep", "kind": "transcript",
                "modified": "2026-07-02T15:00:00Z",
                "meta": {"topic": "Deposition prep",
                         "startTime": "2026-07-02T15:00:00Z",
                         "createTime": "2026-07-02T15:00:00Z",
                         "hostEmail": "jake@firm.example", "meetingId": "mtg1",
                         "playbackUrl": "https://web.webex.com/play/x"}}
        with MockVendor([
            ("GET", "https://webexapis.com/v1/meetingTranscripts/tr1/download",
             FakeResponse(content=vtt)),
        ]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertEqual(name, "Deposition prep (2026-07-02).vtt")
        self.assertEqual(body, vtt)
        dl = v.calls[0]
        self.assertEqual(dl["params"]["format"], "vtt")
        self.assertEqual(dl["headers"]["Authorization"], "Bearer wx-tok")
        self.assertEqual(prov["author"], "jake@firm.example")
        self.assertEqual(prov["date"], "2026-07-02T15:00:00Z")
        self.assertEqual(prov["url"], "https://web.webex.com/play/x")

    def test_bad_token_maps_to_auth_error(self):
        with MockVendor([("GET", "https://webexapis.com/v1/people/me",
                          FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
