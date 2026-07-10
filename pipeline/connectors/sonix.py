"""Sonix (sonix.ai) — transcript library, API key.

Verified against sonix.ai/docs/api (2026-07-10, research_transcription.json):
REST at https://api.sonix.ai/v1, ``Authorization: Bearer <key>``, key copied
from my.sonix.ai/api by any paying subscriber (trial accounts must email
support). ``GET /v1/media`` lists 100 per page with ``total_pages``; only
``status=completed`` media have transcripts. Transcripts download directly
as .vtt via ``GET /v1/media/:id/transcript.vtt`` (speakers + timestamps kept
-> page:line citations). Sonix's signed export/download URLs expire after 30
minutes, so bytes are always fetched immediately and URLs are never stored.
"""

import datetime

import connectors

BASE = "https://api.sonix.ai/v1"

SERVICE = {
    "slug": "sonix",
    "name": "Sonix",
    "category": "Transcription Services",
    "blurb": "Your Sonix transcript library",
    "fields": [{"key": "api_key", "label": "API key", "secret": True}],
    "key_steps": [
        "Log in to Sonix",
        "Open the API page at my.sonix.ai/api",
        "Copy the displayed API key and paste it here",
        "Trial accounts show no key — email support@sonix.ai to request one",
    ],
    "plan_note": "Requires a paid Sonix subscription.",
    "docs_url": "https://sonix.ai/docs/api",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['api_key'].strip()}"}


def _iso(epoch):
    """Sonix created_at (unix epoch seconds) -> ISO 8601, or None."""
    try:
        return datetime.datetime.fromtimestamp(
            int(epoch), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def test(creds):
    data = connectors.get_json(f"{BASE}/media", headers=_headers(creds),
                               params={"page": 1})
    n = len(data.get("media") or [])
    more = (data.get("total_pages") or 1) > 1
    return f"connected — {n}{'+' if more else ''} transcripts visible"


def list_items(creds, since=None):
    items, page = [], 1
    while True:
        data = connectors.get_json(f"{BASE}/media", headers=_headers(creds),
                                   params={"page": page})
        for m in data.get("media") or []:
            if m.get("status") != "completed":
                continue  # transcript fetch requires status=completed
            created = _iso(m.get("created_at"))
            if since and created and created < str(since):
                continue
            items.append({
                "id": str(m.get("id")),
                "name": m.get("name") or "Sonix transcript",
                "kind": "transcript",
                "modified": created,
                "meta": m,
            })
        if page >= (data.get("total_pages") or 1):
            return items
        page += 1


def fetch_item(creds, item):
    m = item["meta"]
    title = item["name"]
    date = _iso(m.get("created_at"))
    prov = {
        "service": "sonix", "title": title, "date": date,
        "author": None,
        "url": None,
    }
    body = connectors.get_bytes(f"{BASE}/media/{item['id']}/transcript.vtt",
                                headers=_headers(creds))
    stamp = (date or "")[:10]
    base = f"{title} ({stamp})" if stamp else title
    return (f"{base}.vtt", body, prov)
