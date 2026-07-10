"""Coda (now Superhuman Docs) — docs exported page-by-page to Markdown.

Verified against the Superhuman Docs API v1.5.0 reference (2026-07-10,
research_notes2.json): Coda was rebranded to Superhuman Docs on 2026-07-08
(Grammarly/Superhuman), docs moved to docs.superhuman.com, but the API base
URL is still https://coda.io/apis/v1 and existing tokens keep working —
keep an eye on deprecation notices. Auth is ``Authorization: Bearer``.
Page content export is ASYNC and per-page: POST
``/docs/{docId}/pages/{pageId}/export`` with ``{"outputFormat": "markdown"}``,
poll ``.../export/{requestId}`` until complete (bounded loop here), then GET
the temporary ``downloadLink`` promptly. A whole doc = its pages exported in
order and concatenated into one .md.
"""

import time

import connectors

BASE = "https://coda.io/apis/v1"
POLL_INTERVAL = 1.0     # seconds between export-status polls
MAX_POLLS = 30          # bound: ~30s per page before we give up

SERVICE = {
    "slug": "coda",
    "name": "Coda",
    "category": "Notes & Docs",
    "blurb": "Docs exported page-by-page to Markdown",
    "fields": [{"key": "token", "label": "API token", "secret": True}],
    "key_steps": [
        "Sign in to Coda (now Superhuman Docs)",
        "Click your avatar in the lower-left corner and choose Account "
        "settings",
        "Scroll to the API settings section",
        "Click Generate API token; name it and (optionally) restrict it to "
        "specific docs or read-only",
        "Copy the token and paste it here",
    ],
    "plan_note": "Works on every plan. Coda rebranded to Superhuman Docs in "
                 "July 2026; existing tokens and this connector keep working.",
    "docs_url": "https://coda.io/developers/apis/v1",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['token'].strip()}"}


def _post_json(url, **kw):
    resp = connectors.request("POST", url, **kw)
    try:
        return resp.json()
    except ValueError:
        raise connectors.ConnectorUnavailable("Coda returned an unreadable "
                                              "response")


def test(creds):
    data = connectors.get_json(f"{BASE}/whoami", headers=_headers(creds))
    name = data.get("name") or "user"
    login = data.get("loginId")
    return f"connected as {name}" + (f" ({login})" if login else "")


def list_items(creds, since=None):
    items, token = [], None
    while True:
        params = {"limit": 100}
        if token:
            params["pageToken"] = token
        data = connectors.get_json(f"{BASE}/docs", headers=_headers(creds),
                                   params=params)
        for doc in data.get("items") or []:
            modified = doc.get("updatedAt")
            if since and modified and str(modified) < str(since):
                continue
            items.append({
                "id": doc["id"],
                "name": doc.get("name") or "Untitled doc",
                "kind": "doc",
                "modified": modified,
                "meta": doc,
            })
        token = data.get("nextPageToken")
        if not token:
            return items


def _doc_pages(creds, doc_id):
    out, token = [], None
    while True:
        params = {"limit": 100}
        if token:
            params["pageToken"] = token
        data = connectors.get_json(f"{BASE}/docs/{doc_id}/pages",
                                   headers=_headers(creds), params=params)
        out.extend(data.get("items") or [])
        token = data.get("nextPageToken")
        if not token:
            return out


def _export_page(creds, doc_id, page_id):
    """Begin markdown export -> poll status (bounded) -> download bytes."""
    begun = _post_json(f"{BASE}/docs/{doc_id}/pages/{page_id}/export",
                       headers=_headers(creds),
                       json_body={"outputFormat": "markdown"})
    request_id = begun.get("id")
    status_url = f"{BASE}/docs/{doc_id}/pages/{page_id}/export/{request_id}"
    for attempt in range(MAX_POLLS):
        status = connectors.get_json(status_url, headers=_headers(creds))
        state = status.get("status")
        if state == "complete":
            link = status.get("downloadLink")
            if not link:
                raise connectors.ConnectorUnavailable(
                    "Coda finished the export but returned no download link")
            # temporary pre-signed link: download promptly, no auth header
            return connectors.get_bytes(link)
        if state == "failed":
            raise connectors.ConnectorUnavailable(
                "Coda could not export this page — try again later")
        if attempt < MAX_POLLS - 1:
            time.sleep(POLL_INTERVAL)
    raise connectors.ConnectorUnavailable(
        "the Coda export did not finish in time — try again later")


def fetch_item(creds, item):
    doc = item["meta"]
    title = item["name"]
    prov = {
        "service": "coda",
        "title": title,
        "date": doc.get("updatedAt") or doc.get("createdAt"),
        "author": doc.get("ownerName") or doc.get("owner"),
        "url": doc.get("browserLink"),
    }
    parts = []
    for page in _doc_pages(creds, item["id"]):
        content = _export_page(creds, item["id"], page["id"])
        text = content.decode("utf-8", errors="replace").strip()
        parts.append(f"## {page.get('name') or 'Page'}\n\n{text}")
    body = f"# {title}\n\n" + "\n\n".join(parts) + "\n"
    return f"{title}.md", body.encode("utf-8"), prov
