"""Rev AI (rev.ai) — developer speech-to-text jobs, personal access token.

Verified against docs.rev.ai (2026-07-10, research_transcription.json):
async API at https://api.rev.ai/speechtotext/v1, ``Authorization: Bearer
<token>`` with the token self-served from the Access Token page (shown once,
max two active). ``GET /account`` validates the key. HONEST LIMIT (stated in
the catalog blurb/plan note too): ``GET /jobs`` only returns jobs submitted
THROUGH THE API within the LAST 30 DAYS — there is no long-lived web library
to pull. Captions download as .vtt via ``GET /jobs/:id/captions`` with
``Accept: text/vtt`` (speakers + timestamps kept -> page:line citations).
"""

import connectors

BASE = "https://api.rev.ai/speechtotext/v1"
PAGE_LIMIT = 100

SERVICE = {
    "slug": "revai",
    "name": "Rev AI",
    "category": "Transcription Services",
    "blurb": "Transcripts of audio submitted through the Rev AI API "
             "(covers the last 30 days only)",
    "fields": [{"key": "api_key", "label": "Access token", "secret": True}],
    "key_steps": [
        "Sign in at rev.ai (a free account works)",
        "Open the Access Token page in the account dashboard",
        "Click Generate New Access Token and confirm in the pop-up",
        "Copy the token immediately — it is shown only once — and paste it here",
    ],
    "plan_note": "Free Rev AI accounts work, but only jobs submitted through "
                 "the API in the last 30 days can be pulled — older "
                 "transcripts are not retrievable.",
    "docs_url": "https://docs.rev.ai/api/asynchronous/reference",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['api_key'].strip()}"}


def test(creds):
    acct = connectors.get_json(f"{BASE}/account", headers=_headers(creds))
    who = acct.get("email") or "account"
    return f"connected — {who}"


def list_items(creds, since=None):
    items, cursor = [], None
    while True:
        params = {"limit": PAGE_LIMIT}
        if cursor:
            params["starting_after"] = cursor
        jobs = connectors.get_json(f"{BASE}/jobs", headers=_headers(creds),
                                   params=params)
        for j in jobs or []:
            if j.get("status") != "transcribed":
                continue  # in-progress or failed jobs have no transcript bytes
            created = j.get("created_on")
            if since and created and str(created) < str(since):
                continue
            items.append({
                "id": str(j.get("id")),
                "name": j.get("name") or f"Rev AI job {j.get('id')}",
                "kind": "transcript",
                "modified": j.get("completed_on") or created,
                "meta": j,
            })
        if not jobs or len(jobs) < PAGE_LIMIT:
            return items
        cursor = jobs[-1].get("id")


def fetch_item(creds, item):
    j = item["meta"]
    title = item["name"]
    stamp = str(j.get("created_on") or "")[:10]
    prov = {
        "service": "revai", "title": title, "date": j.get("created_on"),
        "author": None,
        "url": None,
    }
    headers = _headers(creds)
    headers["Accept"] = "text/vtt"
    body = connectors.get_bytes(f"{BASE}/jobs/{item['id']}/captions",
                                headers=headers)
    base = f"{title} ({stamp})" if stamp else title
    return (f"{base}.vtt", body, prov)
