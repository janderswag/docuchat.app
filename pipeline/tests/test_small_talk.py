"""UX-1 proof: a greeting never triggers retrieval.

small_talk_reply() fires ONLY on whole-message greetings/courtesy/meta phrases and
never on a document-shaped question; /chat and /chat/stream short-circuit to the
canned uncited reply (no retrieval, no 'sources' event) while still persisting the
exchange to the thread. The gate is monkeypatch-proof by construction: the route
tests below assert answer()/answer_stream() are NOT called for small talk."""

import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import catalog  # noqa: E402
import api  # noqa: E402
import routes_chat  # noqa: E402
from answering import small_talk_reply, SMALL_TALK_REPLY  # noqa: E402

client = TestClient(api.app)


class TestSmallTalkDetector(unittest.TestCase):
    def test_greetings_and_meta_fire(self):
        for q in ("hello", "Hello!", " hi ", "HEY", "hello?", "good morning",
                  "are you there?", "Hello, are you there?", "is this working",
                  "thanks", "Thank you!", "who are you", "what can you do",
                  "test", "testing", "what's up", "help", "ok"):
            self.assertEqual(small_talk_reply(q), SMALL_TALK_REPLY, f"should fire: {q!r}")

    def test_document_questions_fall_through(self):
        for q in ("What is the monthly fee under the services agreement?",
                  "hello, what does the engagement letter say about fees?",
                  "termination notice",
                  "who are the parties to the agreement",
                  "test results in the lab report",
                  "hi level indemnification cap",
                  "notice",
                  ""):
            self.assertIsNone(small_talk_reply(q), f"must NOT fire: {q!r}")

    def test_long_messages_never_fire(self):
        self.assertIsNone(small_talk_reply("hello " * 20))

    def test_reply_is_uncited_and_honest(self):
        # The canned reply must not pretend to be grounded: no citation tags.
        self.assertNotIn("[document:", SMALL_TALK_REPLY)
        self.assertNotIn("—", SMALL_TALK_REPLY)  # owner copy rule: no em-dashes


class TestSmallTalkRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls._cat, catalog.DEFAULT_DB = catalog.DEFAULT_DB, cls.tmp / "cat.db"
        catalog.create_matter("Gate Matter")

    @classmethod
    def tearDownClass(cls):
        catalog.DEFAULT_DB = cls._cat

    def setUp(self):
        # If the gate leaks, answer()/answer_stream() would run retrieval — fail loud
        # instead. (Monkeypatched per-test; restored in tearDown.)
        def _boom(*a, **k):
            raise AssertionError("retrieval path invoked for small talk")
        self._answer, routes_chat.answer = routes_chat.answer, _boom
        self._stream, routes_chat.answer_stream = routes_chat.answer_stream, _boom

    def tearDown(self):
        routes_chat.answer = self._answer
        routes_chat.answer_stream = self._stream

    def test_chat_hello_is_canned_uncited_and_persisted(self):
        r = client.post("/chat", json={"question": "hello", "matter": "gate-matter"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["answer_text"], SMALL_TALK_REPLY)
        self.assertEqual(body["citations"], [])
        self.assertTrue(body.get("small_talk"))
        # the exchange still lands in the thread so history stays coherent
        msgs = client.get("/chat/threads/" + str(body["thread_id"])).json()["messages"]
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["content"], SMALL_TALK_REPLY)

    def test_chat_stream_hello_has_no_sources_event(self):
        r = client.post("/chat/stream", json={"question": "hi there",
                                              "matter": "gate-matter"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("event: sources", r.text)
        self.assertIn("event: token", r.text)
        self.assertIn("event: done", r.text)
        self.assertIn("small_talk", r.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
