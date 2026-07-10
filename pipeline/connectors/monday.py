"""monday.com — workdocs rendered to Markdown, personal API token (GraphQL).

Verified against developer.monday.com (2026-07-10, research_notes2.json):
single GraphQL endpoint POST https://api.monday.com/v2, auth is the raw
personal token in ``Authorization`` (no Bearer prefix), with the quarterly
``API-Version`` header pinned. Workdocs are queried at the GraphQL ROOT
(``docs`` cannot be nested inside other queries per vendor docs; limit/page
pagination). Workdoc blocks come back as JSON delta strings, flattened to
readable Markdown here. File/asset downloads are deliberately SKIPPED this
cycle: asset ``public_url`` is a signed link valid only 1 hour. Free/trial
accounts get 1,000 API calls per day, so this adapter is batch-frugal: one
query per page of docs and one per fetched doc.
"""

import json

import connectors

API_URL = "https://api.monday.com/v2"
API_VERSION = "2026-01"
PAGE_SIZE = 25

SERVICE = {
    "slug": "monday",
    "name": "monday.com",
    "category": "Work Management",
    "blurb": "Workdocs rendered to Markdown",
    "fields": [{"key": "token", "label": "Personal API token",
                "secret": True}],
    "key_steps": [
        "Log in to monday.com",
        "Click your profile picture in the top-right corner and select "
        "Developers (opens the Developer Center)",
        "Click API token in the left menu, then Show",
        "Copy your personal token and paste it here",
    ],
    "plan_note": "All plans have API access; free and trial accounts are "
                 "capped at 1,000 calls per day, so a very large first "
                 "import may need to run across days.",
    "docs_url": "https://developer.monday.com/api-reference/docs/authentication",
}


def _gql(creds, query):
    resp = connectors.request(
        "POST", API_URL,
        headers={"Authorization": creds["token"].strip(),
                 "API-Version": API_VERSION},
        json_body={"query": query})
    try:
        data = resp.json()
    except ValueError:
        raise connectors.ConnectorUnavailable("monday.com returned an "
                                              "unreadable response")
    errors = data.get("errors")
    if errors:
        message = "; ".join(e.get("message") or "" for e in errors) or "error"
        if "authenticat" in message.lower():
            raise connectors.ConnectorAuthError(
                "monday.com rejected this token — check that it was copied "
                "completely and has not been regenerated")
        raise connectors.ConnectorError(f"monday.com refused the request "
                                        f"({message})")
    return data.get("data") or {}


def test(creds):
    me = _gql(creds, "{ me { name email } }").get("me") or {}
    name = me.get("name") or "user"
    email = me.get("email")
    return f"connected as {name}" + (f" ({email})" if email else "")


def list_items(creds, since=None):
    items, page = [], 1
    while True:
        data = _gql(creds,
                    f"{{ docs (limit: {PAGE_SIZE}, page: {page}) "
                    f"{{ id object_id name workspace_id url created_at }} }}")
        docs = data.get("docs") or []
        for doc in docs:
            modified = doc.get("created_at")
            if since and modified and str(modified) < str(since):
                continue
            items.append({
                "id": str(doc["id"]),
                "name": doc.get("name") or "Untitled doc",
                "kind": "workdoc",
                "modified": modified,
                "meta": doc,
            })
        if len(docs) < PAGE_SIZE:
            return items
        page += 1


_PREFIX = {
    "large title": "# ",
    "medium title": "## ",
    "small title": "### ",
    "bulleted list": "- ",
    "numbered list": "1. ",
    "check list": "- [ ] ",
    "quote": "> ",
}


def _block_text(content):
    """Workdoc block content is a JSON delta string; flatten to plain text."""
    if not content:
        return ""
    obj = content
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except ValueError:
            return content
    if not isinstance(obj, dict):
        return str(obj)
    delta = obj.get("deltaFormat")
    if isinstance(delta, list):
        return "".join(str(op.get("insert") or "") for op in delta
                       if isinstance(op, dict))
    return str(obj.get("text") or "")


def fetch_item(creds, item):
    data = _gql(creds,
                f"{{ docs (ids: [{item['id']}]) "
                f"{{ id name url created_at blocks {{ id type content }} }} }}")
    docs = data.get("docs") or []
    if not docs:
        raise connectors.ConnectorAccessError(
            "this doc is no longer visible to the token — it may have been "
            "deleted or moved")
    doc = docs[0]
    title = doc.get("name") or item["name"]
    lines = []
    for block in doc.get("blocks") or []:
        text = _block_text(block.get("content"))
        if not text.strip():
            continue
        btype = (block.get("type") or "").lower()
        if btype == "code":
            lines.append(f"```\n{text}\n```")
        else:
            lines.append(_PREFIX.get(btype, "") + text)
    prov = {
        "service": "monday",
        "title": title,
        "date": doc.get("created_at"),
        "url": doc.get("url"),
    }
    body = f"# {title}\n\n" + "\n".join(lines) + "\n"
    return f"{title}.md", body.encode("utf-8"), prov
