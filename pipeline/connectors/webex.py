"""Cisco Webex — meeting transcripts via a personal access token.

Verified against developer.webex.com (2026-07-10, research_meetings.json):
the token is self-served from the developer portal but lives only 12 HOURS —
honest framing: connect, import once, and reconnect with a fresh token to
sync again. Bearer auth throughout. Listing walks GET /v1/recordings and
GET /v1/meetingTranscripts backwards in 30-day from/to windows (date-range
filtered APIs; iterate windows for backfill), following RFC 5988
``Link: rel="next"`` pagination; recordings are joined to transcripts by
meetingId for provenance (topic, createTime, hostEmail, playbackUrl).
Transcript bytes come from GET /v1/meetingTranscripts/{id}/download?format=vtt.
We deliberately never touch temporaryDirectDownloadLinks (they expire 3 hours
after the call and must never be stored). Transcripts only exist when Webex
Assistant / AI Assistant or Closed Captions was on during the meeting.
"""

from datetime import date, timedelta

import connectors

BASE = "https://webexapis.com/v1"
WINDOW_DAYS = 30          # Webex from/to list queries are date-range capped
MONTHS_BACK = 24

SERVICE = {
    "slug": "webex",
    "name": "Cisco Webex",
    "category": "Meeting Platforms",
    "blurb": "Meeting recordings and transcripts",
    "fields": [
        {"key": "access_token", "label": "Personal access token", "secret": True},
    ],
    "key_steps": [
        "Sign in at developer.webex.com with your Webex account",
        "Open the 'Getting your personal access token' docs page (or any API"
        " reference page) — your Bearer token is shown in the token widget",
        "Click copy and paste the token here",
        "The token expires 12 hours after you signed in to the portal — import"
        " right away, and come back for a fresh token when you want to sync again",
    ],
    "plan_note": "Requires a paid Webex Meetings plan with cloud recording; "
                 "transcripts exist only for meetings where Webex Assistant or "
                 "Closed Captions was on. The personal access token lasts 12 "
                 "hours — good for a one-time import; reconnect with a fresh "
                 "token to sync again.",
    "docs_url": "https://developer.webex.com/docs/getting-your-personal-access-token",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['access_token'].strip()}"}


def _next_url(resp):
    """RFC 5988 pagination: the URL from a Link header with rel="next", if any."""
    link = getattr(resp, "headers", {}).get("Link") or ""
    for part in link.split(","):
        if 'rel="next"' in part:
            return part.split(";", 1)[0].strip().strip("<>")
    return None


def _paged(url, headers, params):
    """Yield rows from a Webex list endpoint, following Link: rel="next"."""
    while url:
        resp = connectors.request("GET", url, headers=headers, params=params)
        try:
            data = resp.json()
        except ValueError:
            raise connectors.ConnectorUnavailable(
                "the service returned an unreadable response")
        yield from data.get("items") or []
        url, params = _next_url(resp), None   # next link carries its own query


def test(creds):
    me = connectors.get_json(f"{BASE}/people/me", headers=_headers(creds))
    emails = me.get("emails") or []
    who = me.get("displayName") or (emails[0] if emails else "account")
    return f"connected as {who}"


def list_items(creds, since=None):
    headers = _headers(creds)
    floor = date.today() - timedelta(days=WINDOW_DAYS * MONTHS_BACK)
    if since:
        try:
            floor = max(floor, date.fromisoformat(str(since)[:10]))
        except ValueError:
            pass
    items, seen = [], set()
    to_d = date.today()
    for _ in range(MONTHS_BACK):
        if to_d < floor:
            break
        from_d = max(floor, to_d - timedelta(days=WINDOW_DAYS - 1))
        window = {"from": f"{from_d.isoformat()}T00:00:00Z",
                  "to": f"{to_d.isoformat()}T23:59:59Z", "max": 100}
        rec_by_meeting = {}
        for r in _paged(f"{BASE}/recordings", headers, dict(window)):
            if r.get("meetingId"):
                rec_by_meeting.setdefault(r["meetingId"], r)
        for t in _paged(f"{BASE}/meetingTranscripts", headers, dict(window)):
            tid = str(t.get("id"))
            if not t.get("id") or tid in seen:
                continue
            seen.add(tid)
            rec = rec_by_meeting.get(t.get("meetingId"), {})
            topic = t.get("meetingTopic") or rec.get("topic") or "Webex meeting"
            items.append({
                "id": tid,
                "name": topic,
                "kind": "transcript",
                "modified": t.get("startTime") or rec.get("createTime"),
                "meta": {
                    "topic": topic,
                    "startTime": t.get("startTime"),
                    "createTime": rec.get("createTime"),
                    "hostEmail": t.get("hostEmail") or rec.get("hostEmail"),
                    "meetingId": t.get("meetingId"),
                    "playbackUrl": rec.get("playbackUrl"),
                },
            })
        to_d = from_d - timedelta(days=1)
    return items


def fetch_item(creds, item):
    meta = item["meta"]
    body = connectors.get_bytes(
        f"{BASE}/meetingTranscripts/{item['id']}/download",
        headers=_headers(creds), params={"format": "vtt"})
    title = item["name"]
    stamp = (meta.get("startTime") or meta.get("createTime") or "")[:10]
    base = f"{title} ({stamp})" if stamp else title
    prov = {
        "service": "webex", "title": title,
        "date": meta.get("createTime") or meta.get("startTime"),
        "author": meta.get("hostEmail"), "url": meta.get("playbackUrl"),
        "meeting_id": meta.get("meetingId"),
    }
    return base + ".vtt", body, prov
