"""HubSpot — CRM notes and attached files, private app access token.

Verified against developers.hubspot.com (2026-07-10, research_crm.json):
REST at https://api.hubapi.com, auth ``Authorization: Bearer pat-...``. The
token is a static private-app token any tier including Free can self-serve
(Settings > Integrations > Private Apps; requires a Super Admin; the new
developer docs file private apps under "legacy apps" but they remain
supported). Notes come from the CRM objects API — ``hs_note_body`` is HTML
(capped at 64k) and ``hs_attachment_ids`` names attached files — and render
to .md. File bytes are a two-step: GET /files/v3/files/{id}/signed-url, then
download the returned URL immediately; signed URLs expire and are never
stored.
"""

import html
import re

import connectors

BASE = "https://api.hubapi.com"

SERVICE = {
    "slug": "hubspot",
    "name": "HubSpot",
    "category": "CRM",
    "blurb": "CRM notes and attached files",
    "fields": [{"key": "access_token", "label": "Private app access token",
                "secret": True}],
    "key_steps": [
        "Sign in to HubSpot as a Super Admin (private apps need Super Admin)",
        "Click the Settings gear icon in the top navigation bar",
        "In the left sidebar open Integrations > Private Apps (on portals on "
        "the new developer platform: Development > Legacy apps > Create "
        "legacy app > Private)",
        "Click 'Create a private app' and name it (e.g. 'docuchat')",
        "On the Scopes tab click '+ Add new scope' and select: "
        "crm.objects.contacts.read, crm.objects.companies.read, "
        "crm.objects.deals.read, crm.objects.notes.read, and files",
        "Click 'Create app', confirm, then click 'Show token' and copy it here",
    ],
    "plan_note": "Works on every HubSpot tier, including Free; creating the "
                 "private app requires a Super Admin.",
    "docs_url": "https://developers.hubspot.com/docs/apps/legacy-apps/private-apps/overview",
}

_NOTE_PROPS = ("hs_note_body,hs_attachment_ids,hs_timestamp,hubspot_owner_id,"
               "hs_createdate,hs_lastmodifieddate")


def _headers(creds):
    return {"Authorization": f"Bearer {creds['access_token'].strip()}"}


def _strip_html(text):
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def test(creds):
    data = connectors.get_json(f"{BASE}/account-info/v3/details",
                               headers=_headers(creds))
    portal = data.get("portalId") or data.get("portal_id") or "unknown"
    return f"connected to HubSpot portal {portal}"


def list_items(creds, since=None):
    items = []
    after = None
    while True:                                   # notes, cursor-paginated
        params = {"limit": 100, "properties": _NOTE_PROPS,
                  "associations": "contacts,companies,deals"}
        if after:
            params["after"] = after
        data = connectors.get_json(f"{BASE}/crm/v3/objects/notes",
                                   headers=_headers(creds), params=params)
        for n in data.get("results") or []:
            p = n.get("properties") or {}
            modified = p.get("hs_lastmodifieddate") or n.get("updatedAt")
            if since and modified and modified < since:
                continue
            body = _strip_html(p.get("hs_note_body") or "")
            first = body.splitlines()[0][:80] if body else ""
            items.append({"id": f"note:{n['id']}",
                          "name": first or f"HubSpot note {n['id']}",
                          "kind": "note", "modified": modified, "meta": n})
        after = ((data.get("paging") or {}).get("next") or {}).get("after")
        if not after:
            break
    after = None
    while True:                                   # file manager, same cursor
        params = {"limit": 100}
        if after:
            params["after"] = after
        data = connectors.get_json(f"{BASE}/files/v3/files/search",
                                   headers=_headers(creds), params=params)
        for f in data.get("results") or []:
            modified = f.get("updatedAt") or f.get("createdAt")
            if since and modified and modified < since:
                continue
            items.append({"id": f"file:{f['id']}", "name": _file_name(f),
                          "kind": "file", "modified": modified, "meta": f})
        after = ((data.get("paging") or {}).get("next") or {}).get("after")
        if not after:
            break
    return items


def _file_name(meta):
    name = meta.get("name") or f"HubSpot file {meta.get('id')}"
    ext = (meta.get("extension") or "").lstrip(".")
    if ext and not name.lower().endswith(f".{ext.lower()}"):
        return f"{name}.{ext}"
    return name


def fetch_item(creds, item):
    meta = item["meta"]
    if item["kind"] == "file":
        fid = meta["id"]
        signed = connectors.get_json(f"{BASE}/files/v3/files/{fid}/signed-url",
                                     headers=_headers(creds))
        # download right away and never keep the URL — signed URLs expire;
        # the URL itself is the credential, so no auth header goes with it
        blob = connectors.get_bytes(signed["url"])
        name = _file_name(meta)
        prov = {"service": "hubspot", "title": name,
                "date": meta.get("createdAt"), "modified": meta.get("updatedAt"),
                "author": meta.get("createdBy"), "url": meta.get("url")}
        return name, blob, prov
    p = meta.get("properties") or {}
    body = _strip_html(p.get("hs_note_body") or "")
    linked = []
    for kind, assoc in sorted((meta.get("associations") or {}).items()):
        ids = [r.get("id") for r in (assoc or {}).get("results") or []
               if r.get("id")]
        if ids:
            linked.append(f"{kind} {', '.join(ids)}")
    created = p.get("hs_createdate") or p.get("hs_timestamp") or meta.get("createdAt")
    stamp = (created or "")[:10]
    title = item["name"]
    lines = [f"# {title}", ""]
    if linked:
        lines += ["Linked records: " + "; ".join(linked), ""]
    lines.append(body or "(empty note)")
    prov = {"service": "hubspot", "title": title, "date": created,
            "modified": p.get("hs_lastmodifieddate"),
            "author": p.get("hubspot_owner_id")}
    base = f"HubSpot note {meta['id']}" + (f" ({stamp})" if stamp else "")
    return f"{base}.md", ("\n".join(lines) + "\n").encode("utf-8"), prov
