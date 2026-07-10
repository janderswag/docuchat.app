"""ClickUp — Doc pages as Markdown, personal API token.

Verified against developer.clickup.com (2026-07-10, research_notes2.json):
personal tokens (prefix ``pk_``) are sent as ``Authorization: <token>`` with
NO Bearer prefix — that is the documented scheme for personal tokens. Two
base paths in one connector: workspaces come from v2 (``/api/v2/team``),
Docs from v3 (``/api/v3/workspaces/{id}/docs``, cursor pagination via
``next_cursor``; page tree via ``.../docs/{docId}/pageListing``). Page
content is fetched with ``content_format=text/md`` (the only formats are
text/md and text/plain) — vendor notes the markdown is slightly lossy for
embeds. Works on Free Forever; 100 requests/minute on that plan.
"""

from datetime import datetime, timezone

import connectors

V2 = "https://api.clickup.com/api/v2"
V3 = "https://api.clickup.com/api/v3"

SERVICE = {
    "slug": "clickup",
    "name": "ClickUp",
    "category": "Work Management",
    "blurb": "ClickUp Doc pages, saved as Markdown",
    "fields": [{"key": "token", "label": "Personal API token (pk_...)",
                "secret": True}],
    "key_steps": [
        "Log in to ClickUp",
        "Click your avatar in the upper-right corner and select Settings",
        "Click Apps in the sidebar",
        "Under API Token, click Generate (or Regenerate)",
        "Click Copy and paste the token (it starts with pk_) here",
    ],
    "plan_note": "Works on Free Forever (100 requests/minute). Doc markdown "
                 "export can drop a few embed-style blocks.",
    "docs_url": "https://developer.clickup.com/docs/authentication",
}


def _headers(creds):
    # Personal tokens use the raw token, NOT "Bearer <token>".
    return {"Authorization": creds["token"].strip()}


def _iso(ms):
    try:
        ms = int(ms)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def test(creds):
    data = connectors.get_json(f"{V2}/user", headers=_headers(creds))
    user = data.get("user") or {}
    name = user.get("username") or "user"
    email = user.get("email")
    return f"connected as {name}" + (f" ({email})" if email else "")


def _docs(creds, workspace_id):
    out, cursor = [], None
    while True:
        params = {"limit": 50}
        if cursor:
            params["next_cursor"] = cursor
        data = connectors.get_json(f"{V3}/workspaces/{workspace_id}/docs",
                                   headers=_headers(creds), params=params)
        out.extend(data.get("docs") or [])
        cursor = data.get("next_cursor")
        if not cursor:
            return out


def _flatten_pages(pages):
    flat = []
    for page in pages or []:
        flat.append(page)
        flat.extend(_flatten_pages(page.get("pages")))
    return flat


def list_items(creds, since=None):
    items = []
    teams = connectors.get_json(f"{V2}/team",
                                headers=_headers(creds)).get("teams") or []
    for team in teams:
        for doc in _docs(creds, team["id"]):
            tree = connectors.get_json(
                f"{V3}/workspaces/{team['id']}/docs/{doc['id']}/pageListing",
                headers=_headers(creds))
            modified = _iso(doc.get("date_updated") or doc.get("date_created"))
            if since and modified and str(modified) < str(since):
                continue
            for page in _flatten_pages(tree):
                items.append({
                    "id": page["id"],
                    "name": page.get("name") or "Untitled page",
                    "kind": "doc_page",
                    "modified": modified,
                    "meta": {
                        "workspace_id": team["id"],
                        "workspace_name": team.get("name"),
                        "doc_id": doc["id"],
                        "doc_name": doc.get("name"),
                    },
                })
    return items


def fetch_item(creds, item):
    meta = item["meta"]
    page = connectors.get_json(
        f"{V3}/workspaces/{meta['workspace_id']}/docs/{meta['doc_id']}"
        f"/pages/{item['id']}",
        headers=_headers(creds), params={"content_format": "text/md"})
    title = page.get("name") or item["name"]
    prov = {
        "service": "clickup",
        "title": title,
        "date": _iso(page.get("date_updated") or page.get("date_created")),
        "author": None,
        "url": None,
        "doc": meta.get("doc_name"),
        "workspace": meta.get("workspace_name"),
    }
    body = f"# {title}\n\n{(page.get('content') or '').strip()}\n"
    doc_name = meta.get("doc_name") or "Doc"
    return f"{doc_name} - {title}.md", body.encode("utf-8"), prov
