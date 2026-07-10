"""Zoho CRM — record attachments from Leads/Contacts/Deals, Self Client OAuth.

Verified against zoho.com/crm/developer/docs v8 (2026-07-10, research_crm.json):
the Self Client in the Zoho API console is the documented self-serve
credential for "fetch data from your own account". The user pastes client_id
+ client_secret + a grant code that dies in 3-10 minutes, so ``prepare()``
exchanges it ONCE at connect time for a non-expiring refresh token — that is
what gets sealed. Every later operation mints a 1-hour access token from the
refresh token (once per operation, then reused: the token endpoint is
separately rate-limited). Auth header is ``Zoho-oauthtoken`` (NOT Bearer).
Accounts host and API host must both match the user's data center. Listing is
bounded: the newest 200 records in each of Leads/Contacts/Deals, then each
record's Attachments; only file-type attachments download (link-type have no
bytes). Empty lists come back as HTTP 204 with no body.
"""

import connectors

_DCS = {
    "com": ("https://accounts.zoho.com", "https://www.zohoapis.com"),
    "eu": ("https://accounts.zoho.eu", "https://www.zohoapis.eu"),
    "in": ("https://accounts.zoho.in", "https://www.zohoapis.in"),
    "com.au": ("https://accounts.zoho.com.au", "https://www.zohoapis.com.au"),
    "jp": ("https://accounts.zoho.jp", "https://www.zohoapis.jp"),
}

_MODULES = (("Leads", "Last_Name"), ("Contacts", "Last_Name"),
            ("Deals", "Deal_Name"))

SERVICE = {
    "slug": "zoho",
    "name": "Zoho CRM",
    "category": "CRM",
    "blurb": "Record attachments from Leads, Contacts, and Deals",
    "fields": [
        {"key": "client_id", "label": "Client ID"},
        {"key": "client_secret", "label": "Client Secret", "secret": True},
        {"key": "grant_code", "label": "Grant code (fresh, under 10 minutes old)",
         "secret": True},
        {"key": "data_center", "label": "Data center (com, eu, in, com.au, jp)"},
    ],
    "key_steps": [
        "Go to api-console.zoho.com and sign in with the Zoho account you use "
        "for CRM. Use the console for your data center: api-console.zoho.eu "
        "(Europe), .in (India), .com.au (Australia), .jp (Japan); enter that "
        "suffix as the data center field here",
        "Click GET STARTED (first visit), hover over the 'Self Client' card, "
        "click CREATE NOW, then CREATE and OK",
        "Open the 'Client Secret' tab and copy the Client ID and Client "
        "Secret into the fields here",
        "Open the 'Generate Code' tab and enter this scope exactly: "
        "ZohoCRM.modules.READ,ZohoCRM.settings.READ",
        "Set Time Duration to 10 minutes (the maximum), add any description, "
        "click CREATE, and pick your organization if prompted",
        "Copy the generated grant code here and connect immediately; the "
        "code expires within the duration you chose",
    ],
    "plan_note": "Every Zoho CRM edition includes API access, including Free "
                 "(5,000 credits/day). The grant code must be pasted within "
                 "10 minutes of generating it.",
    "docs_url": "https://www.zoho.com/crm/developer/docs/api/v8/auth-request.html",
}


def _dc(creds):
    return (creds.get("data_center") or "com").strip().lstrip(".") or "com"


def _bases(creds):
    pair = _DCS.get(_dc(creds))
    if pair is None:
        raise connectors.ConnectorError(
            f"unknown Zoho data center {_dc(creds)!r} — use one of: "
            f"{', '.join(sorted(_DCS))}")
    return pair


def _token_post(accounts_base, params):
    resp = connectors.request("POST", f"{accounts_base}/oauth/v2/token",
                              params=params)
    try:
        return resp.json()
    except ValueError:
        raise connectors.ConnectorUnavailable(
            "Zoho returned an unreadable token response — try again")


def prepare(creds):
    """One-time exchange at connect: short-lived grant code -> refresh token.

    Zoho answers HTTP 200 with an ``error`` field for a dead code, so the
    check is on the body, not the status.
    """
    accounts, _ = _bases(creds)
    data = _token_post(accounts, {
        "grant_type": "authorization_code",
        "code": (creds.get("grant_code") or "").strip(),
        "client_id": (creds.get("client_id") or "").strip(),
        "client_secret": (creds.get("client_secret") or "").strip(),
    })
    if data.get("error") or not data.get("refresh_token"):
        raise connectors.ConnectorAuthError(
            "Zoho rejected the grant code — codes expire within minutes, so "
            "generate a fresh one in the API console and connect right away")
    return {"client_id": creds["client_id"].strip(),
            "client_secret": creds["client_secret"].strip(),
            "refresh_token": data["refresh_token"],
            "data_center": _dc(creds)}


def _mint(creds):
    """Refresh token -> 1-hour access token. Mint once per operation."""
    accounts, _ = _bases(creds)
    data = _token_post(accounts, {
        "grant_type": "refresh_token",
        "refresh_token": creds["refresh_token"],
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
    })
    if data.get("error") or not data.get("access_token"):
        raise connectors.ConnectorAuthError(
            "Zoho no longer accepts this connection — it may have been "
            "revoked under Zoho Accounts > Connected Apps; disconnect here "
            "and connect again")
    return data["access_token"]


def _headers(token):
    return {"Authorization": f"Zoho-oauthtoken {token}"}


def _get_json_maybe(url, token, params=None):
    """GET that tolerates Zoho's empty-list answer: HTTP 204, no body."""
    resp = connectors.request("GET", url, headers=_headers(token),
                              params=params)
    if resp.status_code == 204 or not resp.content:
        return {}
    try:
        return resp.json()
    except ValueError:
        return {}


def test(creds):
    token = _mint(creds)
    _, api = _bases(creds)
    data = _get_json_maybe(f"{api}/crm/v8/org", token)
    org = (data.get("org") or [{}])[0]
    name = org.get("company_name") or org.get("primary_email") or "organization"
    return f"connected to {name}"


def list_items(creds, since=None):
    token = _mint(creds)                       # one mint, reused throughout
    _, api = _bases(creds)
    items = []
    for module, name_field in _MODULES:        # newest 200 records per module
        recs = _get_json_maybe(f"{api}/crm/v8/{module}", token, params={
            "fields": f"{name_field},Modified_Time",
            "per_page": 200, "page": 1,
            "sort_by": "Modified_Time", "sort_order": "desc",
        }).get("data") or []
        for rec in recs:
            atts = _get_json_maybe(
                f"{api}/crm/v8/{module}/{rec['id']}/Attachments",
                token).get("data") or []
            for att in atts:
                if att.get("$link_url"):
                    continue                   # link-type: no bytes to fetch
                modified = att.get("Modified_Time") or att.get("Created_Time")
                if since and modified and modified < since:
                    continue
                items.append({
                    "id": f"{module}/{rec['id']}/{att['id']}",
                    "name": att.get("File_Name") or f"Zoho attachment {att['id']}",
                    "kind": "attachment",
                    "modified": modified,
                    "meta": {"module": module, "record_id": rec["id"],
                             "record_name": rec.get(name_field),
                             "attachment": att},
                })
    return items


def fetch_item(creds, item):
    token = _mint(creds)
    _, api = _bases(creds)
    meta = item["meta"]
    att = meta.get("attachment") or {}
    att_id = att.get("id") or item["id"].rsplit("/", 1)[-1]
    blob = connectors.get_bytes(
        f"{api}/crm/v8/{meta['module']}/{meta['record_id']}/Attachments/{att_id}",
        headers=_headers(token))
    owner = att.get("Owner")
    prov = {"service": "zoho", "title": item["name"],
            "date": att.get("Created_Time"),
            "modified": att.get("Modified_Time"),
            "author": owner.get("name") if isinstance(owner, dict) else owner,
            "parent": f"{meta['module']}: "
                      f"{meta.get('record_name') or meta['record_id']}"}
    return item["name"], blob, prov
