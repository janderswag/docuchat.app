"""Trint — transcript library, Key ID + Key Secret over HTTP Basic.

Verified against dev.trint.com (2026-07-10, research_transcription.json):
REST at https://api.trint.com. Modern keys (post-Oct 2024) are a Key ID +
Key Secret pair sent as HTTP Basic auth — some export reference pages still
document the legacy single-value ``api-key`` header, but legacy keys do not
work with the newer APIs, so this adapter follows the current documented
Basic-auth path only. ``GET /transcripts/`` lists with skip/limit
pagination (limit default 100, max 1000). Exports are per-format GETs;
``GET /export/webvtt/:id`` is preferred — it returns .vtt content directly
with speakers enabled (speakers + timestamps kept -> page:line citations).
"""

import connectors

BASE = "https://api.trint.com"
PAGE_LIMIT = 100

SERVICE = {
    "slug": "trint",
    "name": "Trint",
    "category": "Transcription Services",
    "blurb": "Your Trint transcript library",
    "fields": [
        {"key": "key_id", "label": "API Key ID", "secret": False},
        {"key": "key_secret", "label": "API Key Secret", "secret": True},
    ],
    "key_steps": [
        "Log in to Trint",
        "Go to Account settings > API at app.trint.com/account/api "
        "(EU tenant: app.eu.trint.com/account/api)",
        "Create a new API key and choose the USER key type",
        "Copy the Key ID and Key Secret — the secret is shown only at "
        "creation — and paste both here",
    ],
    "plan_note": "The Trint API is accessible on many Trint plans; heavy "
                 "usage requires an Enterprise account.",
    "docs_url": "https://dev.trint.com/",
}


def _auth(creds):
    return (creds["key_id"].strip(), creds["key_secret"].strip())


def test(creds):
    connectors.get_json(f"{BASE}/transcripts/", auth=_auth(creds),
                        params={"limit": 1})
    return "connected — transcript library reachable"


def list_items(creds, since=None):
    items, skip = [], 0
    while True:
        data = connectors.get_json(f"{BASE}/transcripts/", auth=_auth(creds),
                                   params={"limit": PAGE_LIMIT, "skip": skip})
        rows = data if isinstance(data, list) else (data.get("files") or [])
        for t in rows:
            created = t.get("createdAt") or t.get("created")
            if since and created and str(created) < str(since):
                continue
            items.append({
                "id": str(t.get("id") or t.get("_id")),
                "name": t.get("title") or "Trint transcript",
                "kind": "transcript",
                "modified": t.get("updatedAt") or created,
                "meta": t,
            })
        if len(rows) < PAGE_LIMIT:
            return items
        skip += PAGE_LIMIT


def fetch_item(creds, item):
    t = item["meta"]
    title = item["name"]
    created = t.get("createdAt") or t.get("created")
    prov = {
        "service": "trint", "title": title, "date": created,
        "author": None,
        "url": None,
    }
    body = connectors.get_bytes(f"{BASE}/export/webvtt/{item['id']}",
                                auth=_auth(creds),
                                params={"enable-speakers": "true"})
    stamp = str(created or "")[:10]
    base = f"{title} ({stamp})" if stamp else title
    return (f"{base}.vtt", body, prov)
