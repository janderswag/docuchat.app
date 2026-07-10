"""Happy Scribe — transcript library, API key, async export flow.

Verified against dev.happyscribe.com (2026-07-10, research_transcription.json):
REST at https://www.happyscribe.com/api/v1, ``Authorization: Bearer <key>``
from Account > Settings > API. Every list call requires an organization_id,
resolved automatically via ``GET /organizations`` — never asked of the user.
``GET /transcriptions`` pages with page/per_page (default 5, max 100, so
per_page=100 is always sent). Downloads use the documented async export
flow: ``POST /exports`` {format, transcription_ids} -> poll
``GET /exports/:id`` until state=ready -> fetch ``download_link``. Format
.vtt is preferred (speakers + timestamps kept -> page:line citations). The
API allows 200 requests/hour, so the poll is gentle, bounded, and fails
honestly on timeout.
"""

import time

import connectors

BASE = "https://www.happyscribe.com/api/v1"
PAGE_SIZE = 100
POLL_ATTEMPTS = 20
POLL_INTERVAL = 3.0  # seconds; ~1 min ceiling, gentle on the 200 req/hr cap

SERVICE = {
    "slug": "happyscribe",
    "name": "Happy Scribe",
    "category": "Transcription Services",
    "blurb": "Your Happy Scribe transcript library",
    "fields": [{"key": "api_key", "label": "API key", "secret": True}],
    "key_steps": [
        "Log in to the Happy Scribe dashboard",
        "Click Account, then Settings",
        "Open the API section",
        "Generate or copy the API token and paste it here",
    ],
    "plan_note": "Works with any Happy Scribe account that has transcripts; "
                 "the API allows 200 requests per hour.",
    "docs_url": "https://dev.happyscribe.com/",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['api_key'].strip()}"}


def _orgs(creds):
    data = connectors.get_json(f"{BASE}/organizations",
                               headers=_headers(creds))
    return data if isinstance(data, list) else (data.get("organizations") or [])


def test(creds):
    orgs = _orgs(creds)
    if not orgs:
        raise connectors.ConnectorAccessError(
            "this key works but no Happy Scribe organization is visible")
    name = orgs[0].get("name") or orgs[0].get("id")
    return f"connected — organization {name}"


def list_items(creds, since=None):
    orgs = _orgs(creds)
    if not orgs:
        raise connectors.ConnectorAccessError(
            "this key works but no Happy Scribe organization is visible")
    org_id = str(orgs[0].get("id"))
    items, page = [], 0  # page is 0-based per the docs
    while True:
        data = connectors.get_json(
            f"{BASE}/transcriptions", headers=_headers(creds),
            params={"organization_id": org_id, "page": page,
                    "per_page": PAGE_SIZE})
        rows = data if isinstance(data, list) else (data.get("results") or [])
        for t in rows:
            created = t.get("createdAt")
            if since and created and str(created) < str(since):
                continue
            items.append({
                "id": str(t.get("id")),
                "name": t.get("name") or "Happy Scribe transcript",
                "kind": "transcript",
                "modified": t.get("updatedAt") or created,
                "meta": t,
            })
        if len(rows) < PAGE_SIZE:
            return items
        page += 1


def _json(resp):
    try:
        return resp.json()
    except ValueError:
        raise connectors.ConnectorUnavailable(
            "the service returned an unreadable response")


def fetch_item(creds, item):
    t = item["meta"]
    title = item["name"]
    stamp = str(t.get("createdAt") or "")[:10]
    prov = {
        "service": "happyscribe", "title": title, "date": t.get("createdAt"),
        "author": None,
        "url": None,
    }
    headers = _headers(creds)
    job = _json(connectors.request(
        "POST", f"{BASE}/exports", headers=headers,
        json_body={"format": "vtt", "transcription_ids": [item["id"]]}))
    state, link = job.get("state"), job.get("download_link")
    for _ in range(POLL_ATTEMPTS):
        if state == "ready" and link:
            break
        if state == "failed":
            raise connectors.ConnectorUnavailable(
                "Happy Scribe could not export this transcript")
        time.sleep(POLL_INTERVAL)
        job = connectors.get_json(f"{BASE}/exports/{job.get('id')}",
                                  headers=headers)
        state, link = job.get("state"), job.get("download_link")
    if state != "ready" or not link:
        raise connectors.ConnectorUnavailable(
            "the transcript export did not finish in time — try again in a "
            "few minutes")
    body = connectors.get_bytes(link)  # signed link — fetch immediately
    base = f"{title} ({stamp})" if stamp else title
    return (f"{base}.vtt", body, prov)
