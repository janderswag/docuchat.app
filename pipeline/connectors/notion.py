"""Notion — workspace pages via a self-created internal integration.

Verified against developers.notion.com (2026-07-10, research_notes1.json):
REST at https://api.notion.com/v1, ``Authorization: Bearer`` with the internal
integration secret (new tokens start ``ntn_``, pre-2024 ones ``secret_`` —
treat as opaque, never regex-validate), and the required ``Notion-Version``
header pinned to 2026-03-11. The public API has NO export endpoint: page
content arrives as block JSON from ``GET /v1/blocks/{id}/children``, walked
recursively (bounded depth 6) and rendered to Markdown here. CRITICAL: an
internal integration sees NOTHING until the user shares each top-level page
with it (••• menu > Connections) — an empty list almost always means the
sharing step was skipped, not a bad key. Works on the Free plan.
"""

import connectors

BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"
MAX_DEPTH = 6

SERVICE = {
    "slug": "notion",
    "name": "Notion",
    "category": "Notes & Docs",
    "blurb": "Workspace pages and sub-pages, rendered to Markdown",
    "fields": [{"key": "token", "label": "Internal integration secret",
                "secret": True}],
    "key_steps": [
        "Go to notion.so/my-integrations (you must be a workspace owner)",
        "Click + New integration, name it, pick your workspace, and choose "
        "type Internal",
        "On the Configuration tab, under Internal Integration Secret, click "
        "Show, then Copy, and paste the secret here",
        "IMPORTANT: back in Notion, open EACH top-level page you want to "
        "import, click the ••• menu (top right) > Connections, and select "
        "this integration. The integration sees nothing until a page is "
        "shared this way; access cascades to its sub-pages",
    ],
    "plan_note": "Works on the Free plan. Only pages explicitly shared with "
                 "the integration (last step) are visible.",
    "docs_url": "https://developers.notion.com/guides/get-started/authorization",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['token'].strip()}",
            "Notion-Version": NOTION_VERSION}


def _post_json(url, **kw):
    resp = connectors.request("POST", url, **kw)
    try:
        return resp.json()
    except ValueError:
        raise connectors.ConnectorUnavailable("Notion returned an unreadable "
                                              "response")


def test(creds):
    data = connectors.get_json(f"{BASE}/users/me", headers=_headers(creds))
    name = data.get("name") or "integration"
    ws = (data.get("bot") or {}).get("workspace_name")
    return f"connected as {name}" + (f" ({ws})" if ws else "")


def _rich_text(rich):
    return "".join(t.get("plain_text") or "" for t in rich or [])


def _page_title(page):
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            title = _rich_text(prop.get("title"))
            if title:
                return title
    return "Untitled"


def list_items(creds, since=None):
    items, cursor = [], None
    while True:
        body = {"filter": {"property": "object", "value": "page"},
                "page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = _post_json(f"{BASE}/search", headers=_headers(creds),
                          json_body=body)
        for page in data.get("results") or []:
            if page.get("object") != "page":
                continue
            modified = page.get("last_edited_time")
            if since and modified and str(modified) < str(since):
                continue
            items.append({
                "id": page["id"],
                "name": _page_title(page),
                "kind": "page",
                "modified": modified,
                "meta": page,
            })
        if not data.get("has_more"):
            return items
        cursor = data.get("next_cursor")


def _children(creds, block_id):
    out, cursor = [], None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        data = connectors.get_json(f"{BASE}/blocks/{block_id}/children",
                                   headers=_headers(creds), params=params)
        out.extend(data.get("results") or [])
        if not data.get("has_more"):
            return out
        cursor = data.get("next_cursor")


def _render_table(creds, block, depth):
    if depth >= MAX_DEPTH or not block.get("has_children"):
        return []
    rows = [_children_cells(r) for r in _children(creds, block["id"])
            if r.get("type") == "table_row"]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    lines = []
    for i, cells in enumerate(rows):
        cells = cells + [""] * (width - len(cells))
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0:
            lines.append("|" + " --- |" * width)
    return lines


def _children_cells(row_block):
    cells = (row_block.get("table_row") or {}).get("cells") or []
    return [_rich_text(c) for c in cells]


def _render_blocks(creds, blocks, depth=0, indent=""):
    """Block JSON -> Markdown lines. Nested children indented two spaces."""
    lines = []
    for block in blocks:
        btype = block.get("type") or ""
        payload = block.get(btype) or {}
        text = _rich_text(payload.get("rich_text"))
        skip_children = False
        if btype == "heading_1":
            lines += [f"{indent}# {text}", ""]
        elif btype == "heading_2":
            lines += [f"{indent}## {text}", ""]
        elif btype == "heading_3":
            lines += [f"{indent}### {text}", ""]
        elif btype == "paragraph":
            if text:
                lines += [f"{indent}{text}", ""]
        elif btype == "bulleted_list_item":
            lines.append(f"{indent}- {text}")
        elif btype == "numbered_list_item":
            lines.append(f"{indent}1. {text}")
        elif btype == "to_do":
            box = "[x]" if payload.get("checked") else "[ ]"
            lines.append(f"{indent}- {box} {text}")
        elif btype == "quote":
            lines += [f"{indent}> {text}", ""]
        elif btype == "toggle":
            lines.append(f"{indent}{text}")
        elif btype == "code":
            lang = payload.get("language") or ""
            lines += [f"{indent}```{lang}", f"{indent}{text}",
                      f"{indent}```", ""]
            skip_children = True
        elif btype == "table":
            lines += _render_table(creds, block, depth) + [""]
            skip_children = True
        elif btype == "child_page":
            lines += [f"{indent}{payload.get('title') or ''}", ""]
            skip_children = True
        elif btype == "divider":
            lines += [f"{indent}---", ""]
        elif text:
            # unknown block type: keep its plain text, drop nothing silently
            lines += [f"{indent}{text}", ""]
        if (block.get("has_children") and not skip_children
                and depth < MAX_DEPTH):
            kids = _children(creds, block["id"])
            lines.extend(_render_blocks(creds, kids, depth + 1, indent + "  "))
    return lines


def fetch_item(creds, item):
    page = item["meta"]
    title = item["name"]
    prov = {
        "service": "notion",
        "title": title,
        "date": page.get("last_edited_time") or page.get("created_time"),
        "author": (page.get("created_by") or {}).get("id"),
        "url": page.get("url"),
    }
    lines = _render_blocks(creds, _children(creds, item["id"]))
    body = f"# {title}\n\n" + "\n".join(lines).strip() + "\n"
    return f"{title}.md", body.encode("utf-8"), prov
