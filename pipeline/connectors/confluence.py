"""Confluence Cloud (Atlassian) — pages via a self-served API token.

Verified against developer.atlassian.com (2026-07-10, research_notes1.json):
REST v2 at https://<site>.atlassian.net/wiki/api/v2, HTTP Basic auth with
username = account email and password = API token (Cloud only; Server/Data
Center uses a different scheme). Page GET returns an EMPTY body unless the
``body-format`` query param is passed — we request ``storage`` (XHTML) and
save it wrapped in minimal HTML. There is no REST markdown/PDF export.
Tokens expire (365-day maximum; legacy non-expiring tokens are being force
expired through 2026), so the user will need to reconnect with a fresh token.
"""

from urllib.parse import parse_qs, urlparse
import html as _html

import connectors

SERVICE = {
    "slug": "confluence",
    "name": "Confluence",
    "category": "Notes & Docs",
    "blurb": "Confluence Cloud wiki pages, saved as HTML",
    "fields": [
        {"key": "site", "label": "Site (your-team.atlassian.net)"},
        {"key": "email", "label": "Atlassian account email"},
        {"key": "api_token", "label": "API token", "secret": True},
    ],
    "key_steps": [
        "Sign in, then open id.atlassian.com/manage-profile/security/"
        "api-tokens (avatar > Manage account > Security > Create and manage "
        "API tokens)",
        "Click Create API token (choose 'API token with scopes' for least "
        "privilege, e.g. read:page:confluence and read:space:confluence)",
        "Name the token and pick an expiry date (1 to 365 days)",
        "Click Create, then Copy to clipboard (the token is shown only once)",
        "Enter your site address (your-team.atlassian.net), your account "
        "email, and the token here",
    ],
    "plan_note": "Works on Confluence Cloud Free. Atlassian tokens expire "
                 "(365 days maximum), so plan to reconnect with a fresh "
                 "token when yours does.",
    "docs_url": "https://developer.atlassian.com/cloud/confluence/rest/v2/"
                "api-group-page/",
}


def _base(creds):
    site = (creds.get("site") or "").strip()
    site = site.replace("https://", "").replace("http://", "")
    site = site.split("/")[0]
    return f"https://{site}"


def _auth(creds):
    return (creds["email"].strip(), creds["api_token"].strip())


def test(creds):
    data = connectors.get_json(f"{_base(creds)}/wiki/rest/api/user/current",
                               auth=_auth(creds))
    return f"connected as {data.get('displayName') or data.get('accountId')}"


def _next_cursor(data):
    nxt = (data.get("_links") or {}).get("next")
    if not nxt:
        return None
    cursors = parse_qs(urlparse(nxt).query).get("cursor")
    return cursors[0] if cursors else None


def list_items(creds, since=None):
    base = _base(creds)
    items, cursor = [], None
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        data = connectors.get_json(f"{base}/wiki/api/v2/pages",
                                   auth=_auth(creds), params=params)
        for page in data.get("results") or []:
            modified = ((page.get("version") or {}).get("createdAt")
                        or page.get("createdAt"))
            if since and modified and str(modified) < str(since):
                continue
            items.append({
                "id": str(page["id"]),
                "name": page.get("title") or "Untitled page",
                "kind": "page",
                "modified": modified,
                "meta": page,
            })
        cursor = _next_cursor(data)
        if not cursor:
            return items


def fetch_item(creds, item):
    base = _base(creds)
    page = connectors.get_json(f"{base}/wiki/api/v2/pages/{item['id']}",
                               auth=_auth(creds),
                               params={"body-format": "storage"})
    title = page.get("title") or item["name"]
    storage = ((page.get("body") or {}).get("storage") or {}).get("value") or ""
    webui = (page.get("_links") or {}).get("webui")
    prov = {
        "service": "confluence",
        "title": title,
        "date": ((page.get("version") or {}).get("createdAt")
                 or page.get("createdAt")),
        "author": page.get("authorId"),
        "url": f"{base}/wiki{webui}" if webui else None,
    }
    safe_title = _html.escape(title)
    body = (f"<html><head><meta charset=\"utf-8\">"
            f"<title>{safe_title}</title></head>\n"
            f"<body><h1>{safe_title}</h1>\n{storage}\n</body></html>\n")
    return f"{title}.html", body.encode("utf-8"), prov
