"""Airtable — every table imported as a CSV snapshot, personal access token.

Verified against airtable.com/developers (2026-07-10, research_notes2.json):
REST at https://api.airtable.com/v0, ``Authorization: Bearer`` with a
personal access token (legacy API keys were removed Feb 2024). Bases come
from ``/v0/meta/bases``, table schemas from ``/v0/meta/bases/{id}/tables``,
and rows from ``/v0/{baseId}/{tableId}`` (offset pagination) rendered to one
CSV per table with a stable column order (schema order, then extras).
Row ATTACHMENTS are deliberately NOT imported this cycle: their pre-signed
v5.airtableusercontent.com URLs expire ~2 hours after the API response, so
attachment import belongs to a later cycle with immediate-download plumbing.
Rate limits: 5 req/s per base — the paginator stays sequential.
"""

import csv
import io
import json

import connectors

BASE = "https://api.airtable.com/v0"

SERVICE = {
    "slug": "airtable",
    "name": "Airtable",
    "category": "Work Management",
    "blurb": "Every base table imported as a CSV snapshot",
    "fields": [{"key": "token", "label": "Personal access token",
                "secret": True}],
    "key_steps": [
        "Sign in to Airtable and go to airtable.com/create/tokens (Account "
        "menu > Builder hub > Personal access tokens)",
        "Click Create new token and give it a name",
        "Add the scopes data.records:read and schema.bases:read",
        "Under Access, click Add a base and grant the bases (or whole "
        "workspaces) you want to import",
        "Click Create token and copy it immediately (it is shown only once)",
    ],
    "plan_note": "Works on the Free plan. The token only sees bases granted "
                 "under Access; edit the token at airtable.com/create/tokens "
                 "to add more.",
    "docs_url": "https://airtable.com/developers/web/api/introduction",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['token'].strip()}"}


def test(creds):
    data = connectors.get_json(f"{BASE}/meta/whoami", headers=_headers(creds))
    return f"connected as Airtable user {data.get('id')}"


def _bases(creds):
    out, offset = [], None
    while True:
        params = {}
        if offset:
            params["offset"] = offset
        data = connectors.get_json(f"{BASE}/meta/bases",
                                   headers=_headers(creds), params=params)
        out.extend(data.get("bases") or [])
        offset = data.get("offset")
        if not offset:
            return out


def list_items(creds, since=None):
    items = []
    for base in _bases(creds):
        schema = connectors.get_json(
            f"{BASE}/meta/bases/{base['id']}/tables", headers=_headers(creds))
        for table in schema.get("tables") or []:
            items.append({
                "id": f"{base['id']}:{table['id']}",
                "name": f"{base.get('name')} - {table.get('name')}",
                "kind": "table",
                "modified": None,   # Airtable has no table-level timestamp
                "meta": {
                    "base_id": base["id"],
                    "base_name": base.get("name"),
                    "table_id": table["id"],
                    "table_name": table.get("name"),
                    "fields": [f.get("name") for f in table.get("fields") or []],
                },
            })
    return items


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def fetch_item(creds, item):
    meta = item["meta"]
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        data = connectors.get_json(
            f"{BASE}/{meta['base_id']}/{meta['table_id']}",
            headers=_headers(creds), params=params)
        records.extend(data.get("records") or [])
        offset = data.get("offset")
        if not offset:
            break
    # Stable column order: schema field order first, then any extras in
    # first-seen order (Airtable omits empty fields from record JSON).
    columns = list(meta.get("fields") or [])
    for rec in records:
        for name in (rec.get("fields") or {}):
            if name not in columns:
                columns.append(name)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for rec in records:
        fields = rec.get("fields") or {}
        writer.writerow([_cell(fields.get(col)) for col in columns])
    prov = {
        "service": "airtable",
        "title": item["name"],
        "date": max((r.get("createdTime") or "" for r in records), default=None),
        "url": f"https://airtable.com/{meta['base_id']}/{meta['table_id']}",
    }
    return f"{item['name']}.csv", buf.getvalue().encode("utf-8"), prov
