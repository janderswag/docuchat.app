"""Asana — project attachments, personal access token.

Verified against developers.asana.com (2026-07-10, research_notes2.json):
REST at https://app.asana.com/api/1.0, ``Authorization: Bearer`` with a
personal access token. Listing walks workspaces -> projects (offset-token
pagination via ``next_page.offset``) -> ``GET /attachments?parent={gid}``
with ``opt_fields`` (the compact list omits host/download_url otherwise).
Only attachments hosted on Asana itself (``host == "asana"``) are listed:
externally hosted ones (Google Drive, Box, Vimeo, ...) have a null
``download_url`` and cannot be pulled with an Asana key, so they are
filtered out during listing. ``download_url`` is pre-signed and valid only
~2 MINUTES — fetch_item re-requests the attachment and downloads the bytes
immediately; the URL is never stored.
"""

import connectors

BASE = "https://app.asana.com/api/1.0"
_OPT_FIELDS = "name,host,download_url,permanent_url,size,created_at,parent.name"

SERVICE = {
    "slug": "asana",
    "name": "Asana",
    "category": "Work Management",
    "blurb": "Files attached to your projects and tasks",
    "fields": [{"key": "token", "label": "Personal access token",
                "secret": True}],
    "key_steps": [
        "Log in to Asana and open the developer console at "
        "app.asana.com/0/my-apps (profile photo > Settings > Apps > View "
        "developer console)",
        "Under Personal access tokens, click + Create new token",
        "Enter a description and agree to the API terms",
        "Click Create token and copy it immediately (it is shown only once)",
    ],
    "plan_note": "Works on the free plan (150 requests/minute). Only files "
                 "uploaded to Asana itself are imported; links to Google "
                 "Drive, Box, etc. are skipped.",
    "docs_url": "https://developers.asana.com/docs/personal-access-token",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['token'].strip()}"}


def test(creds):
    data = connectors.get_json(f"{BASE}/users/me",
                               headers=_headers(creds)).get("data") or {}
    name = data.get("name") or "user"
    email = data.get("email")
    return f"connected as {name}" + (f" ({email})" if email else "")


def _paginate(creds, url, params):
    """Asana collection GET with next_page.offset pagination."""
    out, offset = [], None
    while True:
        page_params = dict(params, limit=100)
        if offset:
            page_params["offset"] = offset
        data = connectors.get_json(url, headers=_headers(creds),
                                   params=page_params)
        out.extend(data.get("data") or [])
        offset = (data.get("next_page") or {}).get("offset")
        if not offset:
            return out


def list_items(creds, since=None):
    items = []
    workspaces = connectors.get_json(f"{BASE}/workspaces",
                                     headers=_headers(creds)).get("data") or []
    for ws in workspaces:
        projects = _paginate(creds, f"{BASE}/projects",
                             {"workspace": ws["gid"]})
        for project in projects:
            attachments = _paginate(creds, f"{BASE}/attachments",
                                    {"parent": project["gid"],
                                     "opt_fields": _OPT_FIELDS})
            for att in attachments:
                if att.get("host") != "asana":
                    continue    # externally hosted: no download_url via API
                modified = att.get("created_at")
                if since and modified and str(modified) < str(since):
                    continue
                items.append({
                    "id": att["gid"],
                    "name": att.get("name") or "attachment",
                    "kind": "attachment",
                    "modified": modified,
                    "meta": {
                        "workspace_name": ws.get("name"),
                        "project_name": project.get("name"),
                        "attachment": att,
                    },
                })
    return items


def fetch_item(creds, item):
    # Re-request the attachment: download_url is pre-signed and valid only
    # ~2 minutes, so it must be fresh — then fetch the bytes immediately.
    att = connectors.get_json(f"{BASE}/attachments/{item['id']}",
                              headers=_headers(creds),
                              params={"opt_fields": _OPT_FIELDS}
                              ).get("data") or {}
    url = att.get("download_url")
    if not url:
        raise connectors.ConnectorAccessError(
            "this attachment is hosted outside Asana (for example on Google "
            "Drive or Box), so it cannot be downloaded with an Asana key — "
            "connect that service directly instead")
    body = connectors.get_bytes(url)   # pre-signed: no auth header
    name = att.get("name") or item["name"]
    parent = (att.get("parent") or {}).get("name") \
        or item["meta"].get("project_name")
    prov = {
        "service": "asana",
        "title": name,
        "date": att.get("created_at"),
        "author": None,
        "url": att.get("permanent_url"),
        "parent": parent,
        "project": item["meta"].get("project_name"),
        "workspace": item["meta"].get("workspace_name"),
    }
    return name, body, prov
