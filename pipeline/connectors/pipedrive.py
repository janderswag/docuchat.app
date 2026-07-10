"""Pipedrive — CRM notes and deal/person files, personal API token.

Verified against pipedrive.readme.io + developers.pipedrive.com (2026-07-10,
research_crm.json): every user on every plan has a personal API token two
clicks deep in Personal preferences > API, sent as the ``x-api-token`` header
(NOT Bearer). The token is tied to one user AND one company, so requests go
to that company's own subdomain ({company}.pipedrive.com). Notes and files
are v1-only endpoints with start/limit pagination; note ``content`` is HTML
and renders to .md with deal/person context; file bytes come from
GET /v1/files/{id}/download, which redirects to storage (helpers follow
redirects). Files whose ``remote_location`` is not "pipedrive" (e.g. Google
Drive links) may not return bytes and are skipped.
"""

import html
import re

import connectors

SERVICE = {
    "slug": "pipedrive",
    "name": "Pipedrive",
    "category": "CRM",
    "blurb": "CRM notes and files from deals, people, and organizations",
    "fields": [
        {"key": "api_token", "label": "Personal API token", "secret": True},
        {"key": "company_domain",
         "label": "Company domain (the 'acme' in acme.pipedrive.com)"},
    ],
    "key_steps": [
        "Log in to Pipedrive and click your profile picture in the top-right "
        "corner",
        "Choose 'Company settings', then 'Personal preferences' in the left "
        "sidebar",
        "Open the 'API' tab and copy your personal API token (if the tab is "
        "empty, an admin has switched off API access for your permission set)",
        "Paste the token here along with your company domain, the first part "
        "of your Pipedrive address ({company}.pipedrive.com)",
    ],
    "plan_note": "Works on every Pipedrive plan; the company's daily API "
                 "token budget applies.",
    "docs_url": "https://support.pipedrive.com/en/article/how-can-i-find-my-personal-api-key",
}


def _base(creds):
    d = (creds.get("company_domain") or "").strip().lower()
    d = d.replace("https://", "").replace("http://", "").strip("/")
    if not d:
        raise connectors.ConnectorError(
            "enter your Pipedrive company domain, e.g. acme or "
            "acme.pipedrive.com")
    if "." not in d:
        d += ".pipedrive.com"
    return f"https://{d}/api"


def _headers(creds):
    return {"x-api-token": creds["api_token"].strip()}


def _strip_html(text):
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _pages(creds, path, extra=None):
    """v1 start/limit pagination: follow next_start until the vendor is done."""
    start = 0
    while True:
        params = {"start": start, "limit": 100}
        if extra:
            params.update(extra)
        data = connectors.get_json(f"{_base(creds)}{path}",
                                   headers=_headers(creds), params=params)
        yield from (data.get("data") or [])
        pag = (data.get("additional_data") or {}).get("pagination") or {}
        if not pag.get("more_items_in_collection"):
            return
        start = pag.get("next_start", start + 100)


def _ctx(meta):
    """Deal/person/org names, from nested previews or flat *_name fields."""
    def pick(obj_key, name_key, flat_key):
        obj = meta.get(obj_key)
        nested = obj.get(name_key) if isinstance(obj, dict) else None
        return nested or meta.get(flat_key)
    return (pick("deal", "title", "deal_name"),
            pick("person", "name", "person_name"),
            pick("organization", "name", "org_name"))


def test(creds):
    data = connectors.get_json(f"{_base(creds)}/v1/users/me",
                               headers=_headers(creds))
    me = data.get("data") or {}
    who = me.get("name") or me.get("email") or "user"
    dom = me.get("company_domain")
    return f"connected as {who}" + (f" ({dom}.pipedrive.com)" if dom else "")


def list_items(creds, since=None):
    items = []
    for n in _pages(creds, "/v1/notes"):
        modified = n.get("update_time") or n.get("add_time")
        if since and modified and modified < since:
            continue
        deal, person, org = _ctx(n)
        label = deal or person or org
        items.append({"id": f"note:{n['id']}",
                      "name": f"Note ({label})" if label
                              else f"Pipedrive note {n['id']}",
                      "kind": "note", "modified": modified, "meta": n})
    for f in _pages(creds, "/v1/files", {"sort": "update_time"}):
        loc = f.get("remote_location")
        if loc and loc != "pipedrive":
            continue        # externally hosted; /download may return no bytes
        modified = f.get("update_time") or f.get("add_time")
        if since and modified and modified < since:
            continue
        items.append({"id": f"file:{f['id']}",
                      "name": f.get("file_name") or f"Pipedrive file {f['id']}",
                      "kind": "file", "modified": modified, "meta": f})
    return items


def fetch_item(creds, item):
    meta = item["meta"]
    deal, person, org = _ctx(meta)
    if item["kind"] == "file":
        blob = connectors.get_bytes(
            f"{_base(creds)}/v1/files/{meta['id']}/download",
            headers=_headers(creds))            # redirects followed by helper
        name = meta.get("file_name") or f"Pipedrive file {meta['id']}"
        ext = (meta.get("file_type") or "").lstrip(".")
        if ext and "." not in name:
            name = f"{name}.{ext}"
        prov = {"service": "pipedrive", "title": name,
                "date": meta.get("add_time"), "modified": meta.get("update_time"),
                "author": meta.get("added_by_user_id"),
                "deal": deal, "person": person}
        return name, blob, prov
    stamp = (meta.get("add_time") or "")[:10]
    lines = [f"# {item['name']}", ""]
    context = [f"{label}: {val}" for label, val in
               (("Deal", deal), ("Person", person), ("Organization", org)) if val]
    if context:
        lines += context + [""]
    lines.append(_strip_html(meta.get("content") or "") or "(empty note)")
    user = meta.get("user")
    prov = {"service": "pipedrive", "title": item["name"],
            "date": meta.get("add_time"), "modified": meta.get("update_time"),
            "author": (user.get("name") if isinstance(user, dict) else None)
                      or meta.get("user_id"),
            "deal": deal, "person": person}
    base = f"Pipedrive note {meta['id']}" + (f" ({stamp})" if stamp else "")
    return f"{base}.md", ("\n".join(lines) + "\n").encode("utf-8"), prov
