"""Grain (grain.com) — meeting recordings and transcripts, Personal Access Token.

Verified against developers.grain.com (2026-07-10, research_notetakers2.json):
v2 Public API at https://api.grain.com/_/public-api/v2, ``Authorization:
Bearer <PAT>`` plus the REQUIRED ``Public-Api-Version: 2025-10-31`` header.
The list endpoint is ``POST /v2/recordings`` (filters/cursor in the JSON
body) — NOT a GET. Transcripts download directly as .vtt (speakers +
timestamps kept -> page:line citations) via
``GET /v2/recordings/:id/transcript.vtt``. The API went GA for the Business
plan 2025-12-04; older "beta / select partners" notes are stale.
"""

import connectors

BASE = "https://api.grain.com/_/public-api/v2"
API_VERSION = "2025-10-31"

SERVICE = {
    "slug": "grain",
    "name": "Grain",
    "category": "AI Meeting Notetakers",
    "blurb": "Meeting recordings with speaker transcripts",
    "fields": [{"key": "api_key", "label": "Personal Access Token",
                "secret": True}],
    "key_steps": [
        "Sign in at grain.com",
        "Go to Settings > Integrations and open the API tab",
        "Click to generate a Personal Access Token",
        "Copy the token and paste it here",
    ],
    "plan_note": "Requires the Grain Business plan.",
    "docs_url": "https://developers.grain.com/",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['api_key'].strip()}",
            "Public-Api-Version": API_VERSION}


def _post_json(url, creds, body):
    resp = connectors.request("POST", url, headers=_headers(creds),
                              json_body=body)
    try:
        return resp.json()
    except ValueError:
        raise connectors.ConnectorUnavailable(
            "the service returned an unreadable response")


def test(creds):
    data = _post_json(f"{BASE}/recordings", creds, {})
    n = len(data.get("recordings") or [])
    return f"connected — {n}{'+' if data.get('cursor') else ''} recordings visible"


def list_items(creds, since=None):
    items, cursor = [], None
    while True:
        body = {"include": {"participants": True}}
        if cursor:
            body["cursor"] = cursor
        data = _post_json(f"{BASE}/recordings", creds, body)
        for r in data.get("recordings") or []:
            started = r.get("start_datetime")
            if since and started and str(started) < str(since):
                continue
            items.append({
                "id": str(r.get("id")),
                "name": r.get("title") or "Grain recording",
                "kind": "transcript",
                "modified": r.get("end_datetime") or started,
                "meta": r,
            })
        cursor = data.get("cursor")
        if not cursor:
            return items


def fetch_item(creds, item):
    r = item["meta"]
    title = item["name"]
    stamp = str(r.get("start_datetime") or "")[:10]
    speakers = set()
    for p in r.get("participants") or []:
        name = p.get("name") if isinstance(p, dict) else p
        if name:
            speakers.add(name)
    prov = {
        "service": "grain", "title": title, "date": r.get("start_datetime"),
        "author": (r.get("owner") or {}).get("name")
                  if isinstance(r.get("owner"), dict) else r.get("owner"),
        "url": r.get("url"),
        "speakers": sorted(speakers),
    }
    body = connectors.get_bytes(f"{BASE}/recordings/{item['id']}/transcript.vtt",
                                headers=_headers(creds))
    base = f"{title} ({stamp})" if stamp else title
    return (f"{base}.vtt", body, prov)
