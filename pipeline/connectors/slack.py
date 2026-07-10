"""Slack — documents shared in the user's workspace, via a self-created app.

Verified against docs.slack.dev (2026-07-10, research_email.json): the user
creates their OWN Slack app at api.slack.com/apps (From scratch), grants it
User Token Scopes, installs it to the workspace, and pastes the xoxp User
OAuth Token. Per-user internal apps keep normal rate limits — a single
shared/distributed docuchat app would be capped at 1 req/min, so this is the
correct architecture, not a shortcut.

Slack's Web API returns HTTP 200 with ``{"ok": false, "error": ...}`` on
failure, so every response's ``ok`` field is checked and mapped onto the
connector taxonomy (invalid_auth/token_revoked -> ConnectorAuthError, etc.).
Listing uses files.list, filtered to real document types docuchat can ingest
(Slack's coarse ``types`` buckets — images/zips/pdfs — cannot express
"documents": a .docx has no bucket, so the filter is by filename extension).
Downloads GET the file's url_private WITH the Bearer header — without it
Slack silently returns an HTML login page instead of the file.
"""

import datetime

import connectors

API = "https://slack.com/api"

# Filename extensions docuchat can ingest — files.list is filtered to these.
_DOC_EXTS = (".pdf", ".docx", ".txt", ".md", ".eml", ".html", ".htm",
             ".vtt", ".srt", ".csv", ".json")

SERVICE = {
    "slug": "slack",
    "name": "Slack",
    "category": "Team Chat",
    "blurb": "Documents shared in your Slack workspace",
    "fields": [
        {"key": "token", "label": "User OAuth Token (xoxp-...)",
         "secret": True},
    ],
    "key_steps": [
        "Go to api.slack.com/apps, click Create New App, and choose "
        "From scratch",
        "Name the app (e.g. 'docuchat') and pick your workspace",
        "Open OAuth & Permissions and, under User Token Scopes, add: "
        "channels:history, channels:read, files:read, groups:read",
        "Click Install to Workspace and approve",
        "Copy the User OAuth Token (it starts with xoxp-) and paste it here",
    ],
    "plan_note": "Free Slack plans only expose roughly the last 90 days of "
                 "history to the API. Workspaces with app approval turned on "
                 "need an admin to approve the install.",
    "docs_url": "https://docs.slack.dev/quickstart/",
}

_AUTH_ERRS = {"invalid_auth", "not_authed", "token_revoked", "token_expired",
              "account_inactive"}
_ACCESS_ERRS = {"missing_scope", "no_permission", "not_allowed_token_type",
                "ekm_access_denied"}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['token'].strip()}"}


def _checked(data):
    """Slack returns ok:false in a 200 body — apply the taxonomy ourselves."""
    if data.get("ok"):
        return data
    err = data.get("error") or "unknown_error"
    if err in _AUTH_ERRS:
        raise connectors.ConnectorAuthError(
            "Slack rejected this token — it may have been revoked when the "
            "app was uninstalled; reinstall your app and paste the new "
            "User OAuth Token")
    if err in _ACCESS_ERRS:
        raise connectors.ConnectorAccessError(
            "this Slack token is missing a required permission — add "
            "channels:history, channels:read, files:read, and groups:read "
            "under User Token Scopes, then reinstall the app")
    if err in ("ratelimited", "rate_limited"):
        raise connectors.ConnectorRateLimited(
            "Slack is rate-limiting requests — try again in a few minutes")
    raise connectors.ConnectorError(f"Slack refused the request ({err})")


def _call(method, path, creds, params=None):
    resp = connectors.request(method, f"{API}/{path}",
                              headers=_headers(creds), params=params)
    try:
        data = resp.json()
    except ValueError:
        raise connectors.ConnectorUnavailable(
            "Slack returned an unreadable response")
    return _checked(data)


def _iso(epoch):
    if not epoch:
        return None
    try:
        return datetime.datetime.fromtimestamp(
            int(epoch), datetime.timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def test(creds):
    data = _call("POST", "auth.test", creds)
    return f"{data.get('user') or 'connected'} @ {data.get('team') or 'Slack'}"


def _channel_names(creds):
    """id -> name for the channels the token can see (for provenance)."""
    names, cursor = {}, None
    while True:
        params = {"types": "public_channel,private_channel", "limit": "200"}
        if cursor:
            params["cursor"] = cursor
        data = _call("GET", "conversations.list", creds, params)
        for ch in data.get("channels") or []:
            if ch.get("id"):
                names[ch["id"]] = ch.get("name") or ch["id"]
        cursor = (data.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return names


def list_items(creds, since=None):
    channels = _channel_names(creds)
    items, page = [], 1
    while True:
        params = {"count": "100", "page": str(page)}
        if since:
            params["ts_from"] = str(since)
        data = _call("GET", "files.list", creds, params)
        for f in data.get("files") or []:
            fname = f.get("name") or ""
            # Real documents only (noted exception: filtered at list time so
            # images/archives are never fetched at all).
            if not fname.lower().endswith(_DOC_EXTS):
                continue
            chans = (f.get("channels") or []) + (f.get("groups") or [])
            meta = dict(f)
            meta["channel_names"] = [channels.get(c, c) for c in chans]
            items.append({
                "id": f.get("id"),
                "name": f.get("title") or fname,
                "kind": "file",
                "modified": _iso(f.get("timestamp") or f.get("created")),
                "meta": meta,
            })
        paging = data.get("paging") or {}
        try:
            pages = int(paging.get("pages") or 1)
        except (TypeError, ValueError):
            pages = 1
        if page >= pages:
            return items
        page += 1


def fetch_item(creds, item):
    meta = item.get("meta") or {}
    url = meta.get("url_private_download") or meta.get("url_private")
    if not url:
        raise connectors.ConnectorAccessError(
            "Slack did not provide a download link for this file — the "
            "token's user may not have access to it")
    # The Bearer header is mandatory: without it Slack returns an HTML
    # login page instead of the file bytes.
    body = connectors.get_bytes(url, headers=_headers(creds))
    filename = meta.get("name") or item["name"]
    prov = {
        "service": "slack",
        "title": meta.get("title") or filename,
        "author": meta.get("user"),
        "date": _iso(meta.get("timestamp") or meta.get("created")),
        "url": meta.get("permalink"),
        "channels": meta.get("channel_names") or [],
    }
    return filename, body, prov
