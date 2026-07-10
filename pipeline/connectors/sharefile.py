"""ShareFile (Progress) — client-shared files, self-generated API key.

Verified against api.sharefile.com (2026-07-10, research_storage.json): the
user generates a client_id/client_secret at api.sharefile.com/apikeys and
connects with their own username/password via the documented OAuth2 password
grant (form-encoded POST to https://{subdomain}.sharefile.com/oauth/token;
8-hour access tokens minted per operation — nothing durable is stored beyond
what the user pasted). API base is the SECOND hostname the token response
names ({subdomain}.sf-api.com): /sf/v3 OData — Items(id)/Children with
$top/$skip paging, Items(id)/Download 302-redirects to the bytes. Password
grant fails on SSO-only accounts (honest plan_note).
"""

import connectors

SERVICE = {
    "slug": "sharefile",
    "name": "ShareFile",
    "category": "Cloud File Storage",
    "blurb": "Client-shared files",
    "fields": [
        {"key": "subdomain", "label": "ShareFile subdomain (yourfirm in yourfirm.sharefile.com)"},
        {"key": "username", "label": "ShareFile email"},
        {"key": "password", "label": "ShareFile password", "secret": True},
        {"key": "client_id", "label": "API key client ID", "secret": True},
        {"key": "client_secret", "label": "API key client secret", "secret": True},
    ],
    "key_steps": [
        "Go to api.sharefile.com/apikeys and sign in with your ShareFile account",
        "Create an API key (allow the password grant) and copy the client ID and secret",
        "Enter your ShareFile subdomain, email, and password with the key here",
    ],
    "plan_note": "Works on paid ShareFile plans. Accounts that sign in only "
                 "through SSO cannot use this connection.",
    "docs_url": "https://api.sharefile.com/gettingstarted/oauth2password",
}

_PAGE = 200


def _token(creds):
    """Mint an 8h access token via the documented password grant. Returns
    (api_base, headers)."""
    sub = creds["subdomain"].strip().lower()
    data = connectors.request(
        "POST", f"https://{sub}.sharefile.com/oauth/token",
        form_body={"grant_type": "password", "client_id": creds["client_id"],
                   "client_secret": creds["client_secret"],
                   "username": creds["username"], "password": creds["password"]},
    )
    try:
        tok = data.json()
    except ValueError:
        raise connectors.ConnectorUnavailable("the service returned an "
                                              "unreadable sign-in response")
    if "access_token" not in tok:
        raise connectors.ConnectorAuthError(
            "ShareFile rejected the sign-in — check the subdomain, email, "
            "password, and that the API key allows the password grant")
    apicp = tok.get("apicp") or "sf-api.com"
    base = f"https://{tok.get('subdomain') or sub}.{apicp}/sf/v3"
    return base, {"Authorization": f"Bearer {tok['access_token']}"}


def test(creds):
    base, headers = _token(creds)
    session = connectors.get_json(f"{base}/Sessions", headers=headers)
    who = (session.get("Principal") or {}).get("Email") or creds["username"]
    return f"connected as {who}"


def _walk(base, headers, folder_id, path, out, depth=0):
    if depth > 6 or len(out) >= 2000:
        return
    skip = 0
    while True:
        feed = connectors.get_json(
            f"{base}/Items({folder_id})/Children",
            headers=headers, params={"$top": _PAGE, "$skip": skip})
        entries = feed.get("value") or []
        for it in entries:
            kind = (it.get("odata.type") or "")
            name = it.get("FileName") or it.get("Name") or ""
            if kind.endswith("Folder"):
                _walk(base, headers, it["Id"], f"{path}/{name}", out, depth + 1)
            elif kind.endswith("File"):
                out.append({
                    "id": it["Id"], "name": name, "kind": "file",
                    "modified": it.get("ProgenyEditDate") or it.get("CreationDate"),
                    "meta": {"path": path, "author": it.get("CreatorNameShort"),
                             "created": it.get("CreationDate")},
                })
            if len(out) >= 2000:
                return
        if len(entries) < _PAGE:
            return
        skip += _PAGE


def list_items(creds, since=None):
    base, headers = _token(creds)
    out = []
    _walk(base, headers, "allshared", "", out)
    if not out:                      # personal folders when nothing is shared
        _walk(base, headers, "home", "", out)
    return out


def fetch_item(creds, item):
    base, headers = _token(creds)
    body = connectors.get_bytes(f"{base}/Items({item['id']})/Download",
                                headers=headers)   # 302 -> bytes (redirects on)
    prov = {"title": item["name"], "date": item["meta"].get("created"),
            "author": item["meta"].get("author"),
            "path": item["meta"].get("path")}
    return item["name"], body, prov
