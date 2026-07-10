"""Fireflies.ai — meeting transcripts via the GraphQL API, user API key.

Verified against docs.fireflies.ai (2026-07-10, research_notetakers1.json):
single GraphQL endpoint https://api.fireflies.ai/graphql (every request a
POST), auth ``Authorization: Bearer <api key>`` with the key copied from
Integrations > Fireflies API. Works on every plan including Free (50 API
requests/day — a large backfill may take days on Free). Lists page by
``limit``/``skip`` (max 50); sentences are requested only in the
per-transcript fetch because heavy nested fields across many transcripts in
one query hit the documented complexity limits. Sentences carry per-utterance
speaker + start/end seconds -> .vtt; the summary overview is the .md fallback
when a transcript has no sentences. Bad keys can also surface as a GraphQL
``errors`` envelope on HTTP 200, so _gql maps those to the taxonomy too.
"""

import datetime

import connectors

URL = "https://api.fireflies.ai/graphql"
PAGE = 50

SERVICE = {
    "slug": "fireflies",
    "name": "Fireflies.ai",
    "category": "AI Meeting Notetakers",
    "blurb": "Meeting transcripts, summaries, and action items",
    "fields": [{"key": "api_key", "label": "API key", "secret": True}],
    "key_steps": [
        "Log in at app.fireflies.ai",
        "Click Integrations in the left sidebar",
        "Click Fireflies API",
        "Copy the API key shown on that page and paste it here",
    ],
    "plan_note": "Works on every Fireflies plan, including Free "
                 "(50 API requests per day).",
    "docs_url": "https://docs.fireflies.ai/fundamentals/authorization",
}

_USER_Q = "query { user { user_id name email } }"

_LIST_Q = """query List($limit: Int, $skip: Int, $fromDate: DateTime) {
  transcripts(limit: $limit, skip: $skip, fromDate: $fromDate) {
    id title date duration host_email organizer_email meeting_link
  }
}"""

_FETCH_Q = """query Fetch($id: String!) {
  transcript(id: $id) {
    id title date duration host_email organizer_email meeting_link transcript_url
    meeting_attendees { displayName email }
    speakers { name }
    sentences { index speaker_name text start_time end_time }
    summary { overview action_items }
  }
}"""


def _gql(creds, query, variables=None):
    resp = connectors.request(
        "POST", URL,
        headers={"Authorization": f"Bearer {creds['api_key'].strip()}",
                 "Content-Type": "application/json"},
        json_body={"query": query, "variables": variables or {}})
    try:
        payload = resp.json()
    except ValueError:
        raise connectors.ConnectorUnavailable(
            "the service returned an unreadable response")
    errors = payload.get("errors") or []
    if errors:
        first = errors[0] or {}
        code = str(first.get("code")
                   or (first.get("extensions") or {}).get("code") or "").lower()
        if "auth" in code or "api_key" in code or "forbidden" in code:
            raise connectors.ConnectorAuthError(
                "the service rejected this key — check that it was copied "
                "completely and has not been revoked")
        raise connectors.ConnectorError(
            first.get("message") or "the service refused the request")
    return payload.get("data") or {}


def _stamp(date):
    """Fireflies dates arrive as epoch milliseconds or ISO strings."""
    if isinstance(date, (int, float)):
        dt = datetime.datetime.fromtimestamp(date / 1000.0, datetime.timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(date) if date else None


def _vtt_time(seconds):
    """Fireflies sentence times are seconds (float) from meeting start."""
    if not isinstance(seconds, (int, float)):
        return None
    ms = max(0, int(round(seconds * 1000)))
    return (f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:"
            f"{ms % 60000 // 1000:02d}.{ms % 1000:03d}")


def test(creds):
    user = _gql(creds, _USER_Q).get("user") or {}
    return user.get("email") or user.get("name") or "connected"


def list_items(creds, since=None):
    items, skip = [], 0
    while True:
        variables = {"limit": PAGE, "skip": skip}
        if since:
            variables["fromDate"] = since
        batch = _gql(creds, _LIST_Q, variables).get("transcripts") or []
        for t in batch:
            items.append({
                "id": str(t.get("id")),
                "name": t.get("title") or "Fireflies meeting",
                "kind": "transcript",
                "modified": _stamp(t.get("date")),
                "meta": t,
            })
        if len(batch) < PAGE:
            return items
        skip += PAGE


def fetch_item(creds, item):
    data = _gql(creds, _FETCH_Q, {"id": item["id"]}).get("transcript") or {}
    t = {**(item.get("meta") or {}), **data}
    title = t.get("title") or item["name"]
    date = _stamp(t.get("date"))
    stamp = (date or "")[:10]
    sentences = t.get("sentences") or []
    prov = {
        "service": "fireflies", "title": title, "date": date,
        "author": t.get("host_email") or t.get("organizer_email"),
        "url": t.get("transcript_url") or t.get("meeting_link"),
        "speakers": sorted({s.get("speaker_name") for s in sentences
                            if s.get("speaker_name")})
                    or sorted({sp.get("name") for sp in t.get("speakers") or []
                               if sp.get("name")}),
    }
    base = f"{title} ({stamp})" if stamp else title
    if sentences:
        cues, t_ok = [], True
        for s in sentences:
            start = _vtt_time(s.get("start_time"))
            if start is None:
                t_ok = False
                break
            end = _vtt_time(s.get("end_time"))
            cues.append(f"{start} --> {end or start}\n"
                        f"<v {s.get('speaker_name') or 'Speaker'}>{s.get('text') or ''}")
        if t_ok and cues:
            return (f"{base}.vtt",
                    ("WEBVTT\n\n" + "\n\n".join(cues) + "\n").encode("utf-8"), prov)
        lines = [f"{s.get('speaker_name') or 'Speaker'}: {s.get('text') or ''}"
                 for s in sentences]
        return (f"{base}.txt", "\n".join(lines).encode("utf-8"), prov)
    summary = t.get("summary") or {}
    body = f"# {title}\n\n{summary.get('overview') or ''}\n"
    if summary.get("action_items"):
        body += f"\n## Action items\n\n{summary['action_items']}\n"
    return (f"{base} — summary.md", body.encode("utf-8"), prov)
