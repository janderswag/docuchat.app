"""Adapter proofs for the notetaker batch A (v0.3.0, D-81): Granola,
Fireflies.ai, tl;dv, MeetGeek, Avoma. Canned responses match each vendor's
DOCUMENTED shapes from the 2026-07-10 research pass (research_notetakers1/2),
mocked at the connectors.request layer via the shared harness. No network.
"""

import unittest

from tests.test_adapters import (FakeResponse, MockVendor,
                                 fetch_contract_check, service_contract_check)

import connectors  # noqa: E402  (path set up by tests.test_adapters)


class TestGranola(unittest.TestCase):
    CREDS = {"api_key": "grn_test"}
    NOTE = {
        "id": "not_1", "title": "Pemberton strategy",
        "created_at": "2026-07-01T10:00:00Z",
        "owner": {"email": "jake@firm.example", "name": "Jake"},
        "summary": "Discussed the MSA redlines.",
    }
    TRANSCRIPT = [
        {"speaker": "Jake", "text": "Good morning.",
         "start_timestamp": "2026-07-01T10:00:00Z"},
        {"speaker": "Ana", "text": "Morning, let's begin.",
         "start_timestamp": "2026-07-01T10:00:05Z"},
    ]

    def _mod(self):
        from connectors import granola
        return granola

    def test_service_metadata(self):
        mod = self._mod()
        service_contract_check(self, mod)
        self.assertEqual(mod.SERVICE["slug"], "granola")
        self.assertIn("Business plan", mod.SERVICE["plan_note"])

    def test_auth_header_and_label(self):
        page = FakeResponse(json_data={"notes": [self.NOTE], "hasMore": False})
        with MockVendor([("GET", "https://public-api.granola.ai/v1/notes",
                          page)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("notes", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer grn_test")

    def test_list_paginates_and_emits_note_plus_transcript(self):
        pages = iter([
            FakeResponse(json_data={"notes": [self.NOTE], "hasMore": True,
                                    "cursor": "c2"}),
            FakeResponse(json_data={"notes": [dict(self.NOTE, id="not_2")],
                                    "hasMore": False, "cursor": None}),
        ])
        with MockVendor([("GET", "https://public-api.granola.ai/v1/notes",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual(v.calls[1]["params"].get("cursor"), "c2")
        self.assertEqual([i["id"] for i in items],
                         ["not_1:notes", "not_1", "not_2:notes", "not_2"])
        self.assertEqual({i["kind"] for i in items}, {"note", "transcript"})

    def test_fetch_note_renders_md_with_zero_calls(self):
        item = {"id": "not_1:notes", "name": "Pemberton strategy",
                "kind": "note", "modified": "2026-07-01T10:00:00Z",
                "meta": self.NOTE}
        with MockVendor([]):  # summary rides the list response: no HTTP at all
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".md"))
        self.assertIn(b"Discussed the MSA redlines.", body)
        self.assertEqual(prov["author"], "jake@firm.example")

    def test_fetch_transcript_renders_vtt(self):
        detail = FakeResponse(
            json_data=dict(self.NOTE, transcript=self.TRANSCRIPT))
        item = {"id": "not_1", "name": "Pemberton strategy",
                "kind": "transcript", "modified": "2026-07-01T10:00:00Z",
                "meta": self.NOTE}
        with MockVendor([("GET",
                          "https://public-api.granola.ai/v1/notes/not_1",
                          detail)]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        self.assertEqual(v.calls[0]["params"].get("include"), "transcript")
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        text = body.decode()
        self.assertIn("WEBVTT", text)
        self.assertIn("<v Jake>Good morning.", text)
        self.assertIn("00:00:05.000", text)
        self.assertEqual(prov["speakers"], ["Ana", "Jake"])

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", "https://public-api.granola.ai",
                          FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


class TestFireflies(unittest.TestCase):
    CREDS = {"api_key": "ff-test"}
    GQL = "https://api.fireflies.ai/graphql"
    ROW = {"id": "tr_1", "title": "Pemberton kickoff",
           "date": 1782900000000,  # 2026-07-01T10:00:00Z in epoch ms
           "duration": 1800, "host_email": "jake@firm.example",
           "organizer_email": "jake@firm.example",
           "meeting_link": "https://meet.example/x"}
    DETAIL = dict(
        ROW,
        transcript_url="https://app.fireflies.ai/view/tr_1",
        meeting_attendees=[{"displayName": "Jake",
                            "email": "jake@firm.example"}],
        speakers=[{"name": "Jake"}, {"name": "Ana"}],
        sentences=[
            {"index": 0, "speaker_name": "Jake", "text": "Good morning.",
             "start_time": 0, "end_time": 2.5},
            {"index": 1, "speaker_name": "Ana",
             "text": "Morning, let's begin.",
             "start_time": 2.5, "end_time": 5.0},
        ],
        summary={"overview": "Kickoff overview.",
                 "action_items": "Send the MSA."})

    def _mod(self):
        from connectors import fireflies
        return fireflies

    def test_service_metadata(self):
        mod = self._mod()
        service_contract_check(self, mod)
        self.assertEqual(mod.SERVICE["slug"], "fireflies")
        self.assertIn("Free", mod.SERVICE["plan_note"])

    def test_auth_header_and_whoami_label(self):
        resp = FakeResponse(json_data={"data": {"user": {
            "user_id": "u1", "name": "Jake", "email": "jake@firm.example"}}})
        with MockVendor([("POST", self.GQL, resp)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertEqual(label, "jake@firm.example")
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer ff-test")
        self.assertEqual(v.calls[0]["headers"]["Content-Type"],
                         "application/json")
        self.assertIn("user", v.calls[0]["json_body"]["query"])

    def test_list_paginates_by_limit_skip(self):
        page1 = {"data": {"transcripts":
                          [dict(self.ROW, id=f"tr_{i}") for i in range(50)]}}
        page2 = {"data": {"transcripts": [dict(self.ROW, id="tr_50")]}}
        pages = iter([FakeResponse(json_data=page1),
                      FakeResponse(json_data=page2)])
        with MockVendor([("POST", self.GQL, lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual(len(items), 51)
        self.assertEqual(v.calls[0]["json_body"]["variables"]["skip"], 0)
        self.assertEqual(v.calls[0]["json_body"]["variables"]["limit"], 50)
        self.assertEqual(v.calls[1]["json_body"]["variables"]["skip"], 50)
        self.assertEqual(items[0]["modified"], "2026-07-01T10:00:00Z")

    def test_fetch_renders_vtt_with_speakers(self):
        resp = FakeResponse(json_data={"data": {"transcript": self.DETAIL}})
        item = {"id": "tr_1", "name": "Pemberton kickoff",
                "kind": "transcript", "modified": "2026-07-01T10:00:00Z",
                "meta": self.ROW}
        with MockVendor([("POST", self.GQL, resp)]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        self.assertEqual(v.calls[0]["json_body"]["variables"]["id"], "tr_1")
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        self.assertIn("(2026-07-01)", name)
        text = body.decode()
        self.assertIn("WEBVTT", text)
        self.assertIn("<v Jake>Good morning.", text)
        self.assertIn("00:00:02.500", text)
        self.assertEqual(prov["author"], "jake@firm.example")
        self.assertEqual(prov["url"], "https://app.fireflies.ai/view/tr_1")
        self.assertEqual(prov["speakers"], ["Ana", "Jake"])

    def test_fetch_falls_back_to_summary_md(self):
        detail = dict(self.DETAIL, sentences=[])
        resp = FakeResponse(json_data={"data": {"transcript": detail}})
        item = {"id": "tr_1", "name": "Pemberton kickoff", "kind": "transcript",
                "modified": None, "meta": self.ROW}
        with MockVendor([("POST", self.GQL, resp)]):
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".md"))
        self.assertIn(b"Kickoff overview.", body)
        self.assertIn(b"Send the MSA.", body)

    def test_graphql_error_envelope_maps_auth_code(self):
        resp = FakeResponse(json_data={"errors": [
            {"message": "Invalid API key", "code": "invalid_api_key"}]})
        with MockVendor([("POST", self.GQL, resp)]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("POST", self.GQL, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


class TestTldv(unittest.TestCase):
    CREDS = {"api_key": "tldv-test"}
    BASE = "https://pasta.tldv.io/v1alpha1"
    MEETING = {
        "id": "m1", "name": "Pemberton kickoff",
        "happenedAt": "2026-07-01T10:00:00Z",
        "url": "https://tldv.io/app/meetings/m1", "duration": 1800,
        "organizer": {"name": "Jake", "email": "jake@firm.example"},
        "invitees": [{"name": "Jake", "email": "jake@firm.example"},
                     {"name": "Ana", "email": "ana@client.example"}],
    }
    TRANSCRIPT = {"id": "t1", "meetingId": "m1", "data": [
        {"speaker": "Jake", "text": "Good morning.",
         "startTime": 0, "endTime": 2.5},
        {"speaker": "Ana", "text": "Morning, let's begin.",
         "startTime": 2.5, "endTime": 5},
    ]}
    NOTES = {
        "structuredNotes": [{"segmentId": "s1", "timestamp": 10,
                             "text": "Kickoff recap", "topicId": "t1"}],
        "markdownContent": "## Recap\n\n- Discussed the MSA redlines.",
        "topics": [{"id": "t1", "order": 0, "title": "Recap",
                    "summary": "MSA redlines"}],
    }

    def _mod(self):
        from connectors import tldv
        return tldv

    def test_service_metadata(self):
        mod = self._mod()
        service_contract_check(self, mod)
        self.assertEqual(mod.SERVICE["slug"], "tldv")
        self.assertIn("Pro", mod.SERVICE["plan_note"])
        self.assertIn("organizer", mod.SERVICE["plan_note"])

    def test_auth_header_and_label(self):
        page = FakeResponse(json_data={"page": 0, "pages": 1, "total": 2,
                                       "pageSize": 50,
                                       "results": [self.MEETING]})
        with MockVendor([("GET", f"{self.BASE}/meetings", page)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("2", label)
        self.assertEqual(v.calls[0]["headers"]["x-api-key"], "tldv-test")
        self.assertNotIn("Authorization", v.calls[0]["headers"])

    def test_list_paginates_by_page(self):
        pages = iter([
            FakeResponse(json_data={"page": 0, "pages": 2, "total": 2,
                                    "pageSize": 50,
                                    "results": [self.MEETING]}),
            FakeResponse(json_data={"page": 1, "pages": 2, "total": 2,
                                    "pageSize": 50,
                                    "results": [dict(self.MEETING, id="m2")]}),
        ])
        with MockVendor([("GET", f"{self.BASE}/meetings",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual(v.calls[1]["params"].get("page"), 1)
        self.assertEqual([i["id"] for i in items],
                         ["m1", "m1:notes", "m2", "m2:notes"])

    def test_fetch_transcript_renders_vtt(self):
        item = {"id": "m1", "name": "Pemberton kickoff", "kind": "transcript",
                "modified": "2026-07-01T10:00:00Z", "meta": self.MEETING}
        with MockVendor([("GET", f"{self.BASE}/meetings/m1/transcript",
                          FakeResponse(json_data=self.TRANSCRIPT))]):
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        text = body.decode()
        self.assertIn("WEBVTT", text)
        self.assertIn("<v Jake>Good morning.", text)
        self.assertIn("00:00:02.500", text)
        self.assertEqual(prov["author"], "jake@firm.example")
        self.assertEqual(prov["speakers"], ["Ana", "Jake"])

    def test_fetch_notes_renders_markdown_content(self):
        item = {"id": "m1:notes", "name": "Pemberton kickoff", "kind": "note",
                "modified": "2026-07-01T10:00:00Z", "meta": self.MEETING}
        with MockVendor([("GET", f"{self.BASE}/meetings/m1/notes",
                          FakeResponse(json_data=self.NOTES))]):
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".md"))
        self.assertIn(b"Discussed the MSA redlines.", body)
        self.assertEqual(prov["speakers"], ["Jake", "Ana"])

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", "https://pasta.tldv.io", FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


class TestMeetGeek(unittest.TestCase):
    CREDS = {"api_key": "mg-test", "region": "EU"}
    EU = "https://api.meetgeek.ai"
    US = "https://api-us.meetgeek.ai"
    LISTED = {"meeting_id": "m1",
              "timestamp_start_utc": "2026-07-01T14:00:00Z",
              "timestamp_end_utc": "2026-07-01T14:30:00Z"}
    DETAIL = {"meeting_id": "m1", "title": "Pemberton kickoff",
              "timestamp_start_utc": "2026-07-01T14:00:00Z",
              "participants": [{"name": "John Doe",
                                "email": "john@firm.example"}]}
    TRANSCRIPT = {"meeting_id": "m1", "sentences": [
        {"id": 1, "speaker": "John Doe",
         "timestamp": "2026-07-01T14:00:34Z",
         "transcript": "Previous quarter was great!"},
        {"id": 2, "speaker": "Ana Roe",
         "timestamp": "2026-07-01T14:00:40Z",
         "transcript": "Indeed it was."},
    ], "pagination": {"next_cursor": None}}

    def _mod(self):
        from connectors import meetgeek
        return meetgeek

    def test_service_metadata(self):
        mod = self._mod()
        service_contract_check(self, mod)
        self.assertEqual(mod.SERVICE["slug"], "meetgeek")
        self.assertTrue(any(f["key"] == "region"
                            for f in mod.SERVICE["fields"]))
        self.assertTrue(any("region" in s.lower()
                            for s in mod.SERVICE["key_steps"]))
        self.assertIn("Free", mod.SERVICE["plan_note"])

    def test_auth_header_and_region_routing(self):
        page = FakeResponse(json_data={"meetings": [self.LISTED],
                                       "pagination": {"next_cursor": None}})
        with MockVendor([("GET", f"{self.EU}/v1/meetings", page)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("meetings", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer mg-test")
        with MockVendor([("GET", f"{self.US}/v1/meetings", page)]) as v:
            self._mod().test({"api_key": "mg-test", "region": "US"})
        self.assertTrue(v.calls[0]["url"].startswith(self.US))

    def test_list_paginates_by_cursor(self):
        pages = iter([
            FakeResponse(json_data={"meetings": [self.LISTED],
                                    "pagination": {"next_cursor": "c2"}}),
            FakeResponse(json_data={
                "meetings": [dict(self.LISTED, meeting_id="m2")],
                "pagination": {"next_cursor": None}}),
        ])
        with MockVendor([("GET", f"{self.EU}/v1/meetings",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        self.assertEqual(v.calls[1]["params"].get("cursor"), "c2")
        self.assertEqual([i["id"] for i in items], ["m1", "m2"])
        # sparse list is never followed by per-meeting detail calls (quota)
        self.assertEqual(len(v.calls), 2)
        self.assertIn("2026-07-01 14:00", items[0]["name"])

    def test_fetch_renders_vtt_offset_from_meeting_start(self):
        item = {"id": "m1", "name": "MeetGeek meeting 2026-07-01 14:00",
                "kind": "transcript",
                "modified": "2026-07-01T14:00:00Z", "meta": self.LISTED}
        routes = [
            ("GET", f"{self.EU}/v1/meetings/m1/transcript",
             FakeResponse(json_data=self.TRANSCRIPT)),
            ("GET", f"{self.EU}/v1/meetings/m1",
             FakeResponse(json_data=self.DETAIL)),
        ]
        with MockVendor(routes):
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        self.assertIn("Pemberton kickoff", name)  # title from detail call
        text = body.decode()
        self.assertIn("WEBVTT", text)
        self.assertIn("00:00:34.000", text)  # absolute ISO -> offset clock
        self.assertIn("<v John Doe>Previous quarter was great!", text)
        self.assertEqual(prov["speakers"], ["Ana Roe", "John Doe"])
        self.assertEqual(prov["title"], "Pemberton kickoff")

    def test_fetch_falls_back_to_summary_md(self):
        item = {"id": "m1", "name": "MeetGeek meeting 2026-07-01 14:00",
                "kind": "transcript",
                "modified": "2026-07-01T14:00:00Z", "meta": self.LISTED}
        routes = [
            ("GET", f"{self.EU}/v1/meetings/m1/transcript",
             FakeResponse(json_data={"meeting_id": "m1", "sentences": [],
                                     "pagination": {"next_cursor": None}})),
            ("GET", f"{self.EU}/v1/meetings/m1/summary",
             FakeResponse(json_data={"summary": "Quarterly recap."})),
            ("GET", f"{self.EU}/v1/meetings/m1",
             FakeResponse(json_data=self.DETAIL)),
        ]
        with MockVendor(routes):
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".md"))
        self.assertIn(b"Quarterly recap.", body)

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", self.EU, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


class TestAvoma(unittest.TestCase):
    CREDS = {"api_key": "ck_live:cs_secret"}
    BASE = "https://api.avoma.com"
    MEETING = {
        "uuid": "mu-1", "subject": "Pemberton kickoff",
        "start_at": "2026-07-01T10:00:00Z", "end_at": "2026-07-01T10:30:00Z",
        "duration": 1800.0,
        "attendees": [{"name": "Jake", "email": "jake@firm.example",
                       "response_status": "accepted", "uuid": "a1"}],
        "organizer_email": "jake@firm.example",
        "is_call": False, "is_internal": False, "is_private": False,
        "state": "completed", "processing_status": "processed",
        "transcript_ready": True, "transcription_uuid": "tu-1",
        "notes_ready": True, "recording_uuid": "ru-1",
        "url": "https://app.avoma.com/meetings/mu-1",
    }
    TRANSCRIPTION = {
        "meeting_uuid": "mu-1",
        "speakers": [
            {"id": 1, "name": "Jake", "email": "jake@firm.example",
             "is_rep": True},
            {"id": 2, "name": "Ana", "email": "ana@client.example",
             "is_rep": False},
        ],
        "transcript": [
            {"speaker_id": 1, "transcript": "Good morning.",
             "timestamps": [0.0, 0.6, 1.2]},
            {"speaker_id": 2, "transcript": "Morning, let's begin.",
             "timestamps": [5.0, 5.5, 6.0]},
        ],
    }
    NOTES = {"count": 1, "next": None, "results": [
        {"uuid": "nu-1", "meeting_uuid": "mu-1",
         "data": [{"label": "Action Items",
                   "children": [{"text": "Send the MSA."},
                                {"text": "Review indemnity."}]}]}]}

    def _mod(self):
        from connectors import avoma
        return avoma

    def test_service_metadata(self):
        mod = self._mod()
        service_contract_check(self, mod)
        self.assertEqual(mod.SERVICE["slug"], "avoma")
        self.assertIn("API access", mod.SERVICE["plan_note"])

    def test_auth_header_and_label(self):
        resp = FakeResponse(json_data={"count": 2, "results": [
            {"email": "jake@firm.example"}, {"email": "ana@firm.example"}]})
        with MockVendor([("GET", f"{self.BASE}/v1/users/", resp)]) as v:
            label = self._mod().test(self.CREDS)
        self.assertIn("2", label)
        self.assertEqual(v.calls[0]["headers"]["Authorization"],
                         "Bearer ck_live:cs_secret")

    def test_list_sends_required_window_and_follows_next(self):
        page2_url = f"{self.BASE}/v1/meetings/?page=2"
        pages = iter([
            FakeResponse(json_data={"count": 2, "next": page2_url,
                                    "previous": None,
                                    "results": [self.MEETING]}),
            FakeResponse(json_data={"count": 2, "next": None,
                                    "previous": None,
                                    "results": [dict(self.MEETING,
                                                     uuid="mu-2",
                                                     notes_ready=False)]}),
        ])
        with MockVendor([("GET", f"{self.BASE}/v1/meetings/",
                          lambda call: next(pages))]) as v:
            items = self._mod().list_items(self.CREDS)
        # from_date/to_date are REQUIRED; default window is five years
        params = v.calls[0]["params"]
        self.assertIn("from_date", params)
        self.assertIn("to_date", params)
        self.assertGreaterEqual(int(params["to_date"][:4])
                                - int(params["from_date"][:4]), 4)
        # pagination follows the full ``next`` URL
        self.assertEqual(v.calls[1]["url"], page2_url)
        self.assertEqual(v.calls[1]["params"], {})
        # ready flags decide what is importable
        self.assertEqual([i["id"] for i in items],
                         ["mu-1", "mu-1:notes", "mu-2"])

    def test_fetch_transcript_renders_vtt_via_speaker_map(self):
        item = {"id": "mu-1", "name": "Pemberton kickoff",
                "kind": "transcript", "modified": "2026-07-01T10:00:00Z",
                "meta": self.MEETING}
        with MockVendor([("GET", f"{self.BASE}/v1/transcriptions/tu-1/",
                          FakeResponse(json_data=self.TRANSCRIPTION))]):
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".vtt"))
        text = body.decode()
        self.assertIn("WEBVTT", text)
        self.assertIn("00:00:00.000 --> 00:00:01.200", text)
        self.assertIn("<v Jake>Good morning.", text)
        self.assertIn("00:00:05.000", text)
        self.assertEqual(prov["author"], "jake@firm.example")
        self.assertEqual(prov["speakers"], ["Ana", "Jake"])

    def test_fetch_notes_renders_md(self):
        item = {"id": "mu-1:notes", "name": "Pemberton kickoff",
                "kind": "note", "modified": "2026-07-01T10:00:00Z",
                "meta": self.MEETING}
        with MockVendor([("GET", f"{self.BASE}/v1/notes/",
                          FakeResponse(json_data=self.NOTES))]) as v:
            name, body, prov = self._mod().fetch_item(self.CREDS, item)
        self.assertEqual(v.calls[0]["params"].get("meeting_uuid"), "mu-1")
        self.assertEqual(v.calls[0]["params"].get("output_format"), "json")
        fetch_contract_check(self, name, body, prov)
        self.assertTrue(name.endswith(".md"))
        text = body.decode()
        self.assertIn("## Action Items", text)
        self.assertIn("Send the MSA.", text)
        self.assertEqual(prov["speakers"], ["Jake"])

    def test_bad_key_maps_to_auth_error(self):
        with MockVendor([("GET", self.BASE, FakeResponse(401))]):
            with self.assertRaises(connectors.ConnectorAuthError):
                self._mod().test(self.CREDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
