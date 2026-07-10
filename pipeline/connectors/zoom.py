"""Zoom — cloud-recording transcripts via a user-created Server-to-Server OAuth app.

Verified against developers.zoom.us (2026-07-10, research_meetings.json): the
account owner/admin self-creates an internal Server-to-Server OAuth app at
marketplace.zoom.us (no Zoom review) and pastes the three app credentials
here. Each operation mints a fresh access token — POST zoom.us/oauth/token
with grant_type=account_credentials + HTTP Basic (client id/secret); tokens
last 1h and there is deliberately NO refresh token, so we mint per operation
and never persist one. Listing walks GET /v2/users/me/recordings backwards in
30-day windows (the API's hard max) for 24 months with next_page_token
pagination; only recording_files with file_type TRANSCRIPT (WebVTT) are
imported, downloaded from download_url with a Bearer header. Gotcha: Zoom's
"Audio transcript" recording setting is OFF by default — without it there are
MP4s but no transcripts to import.
"""

from datetime import date, timedelta

import connectors

BASE = "https://api.zoom.us/v2"
TOKEN_URL = "https://zoom.us/oauth/token"
WINDOW_DAYS = 30          # Zoom hard-caps each from/to query at one month
MONTHS_BACK = 24

SERVICE = {
    "slug": "zoom",
    "name": "Zoom",
    "category": "Meeting Platforms",
    "blurb": "Cloud recordings and meeting transcripts",
    "fields": [
        {"key": "account_id", "label": "Account ID", "secret": False},
        {"key": "client_id", "label": "Client ID", "secret": False},
        {"key": "client_secret", "label": "Client Secret", "secret": True},
    ],
    "key_steps": [
        "Sign in at marketplace.zoom.us as the Zoom account owner or admin",
        "Click Develop (top right) > Build App > Server-to-Server OAuth > Create,"
        " and name the app (e.g. docuchat)",
        "Copy the Account ID, Client ID, and Client Secret from the App"
        " Credentials page and paste all three here",
        "On the Information tab, fill in the required app name, company, and"
        " contact fields",
        "On the Scopes tab, add: cloud_recording:read:list_user_recordings:admin,"
        " cloud_recording:read:list_recording_files:admin,"
        " cloud_recording:read:meeting_transcript:admin, and user:read:user:admin",
        "On the Activation tab, click Activate your app (internal app — no Zoom"
        " review)",
        "In Zoom Settings > Recording, make sure 'Audio transcript' is turned on"
        " so future cloud recordings produce transcripts",
    ],
    "plan_note": "Requires a paid Zoom plan (Pro or higher) and an account "
                 "owner/admin role; cloud-recording transcripts must be enabled.",
    "docs_url": "https://developers.zoom.us/docs/internal-apps/",
}


def _bearer(creds):
    """Mint a fresh 1h access token (no refresh tokens exist for this grant).

    Called once per operation (test / list / import); the returned header dict
    is reused for every call within that operation.
    """
    resp = connectors.request(
        "POST", TOKEN_URL,
        params={"grant_type": "account_credentials",
                "account_id": creds["account_id"].strip()},
        auth=(creds["client_id"].strip(), creds["client_secret"].strip()))
    try:
        token = resp.json().get("access_token")
    except ValueError:
        token = None
    if not token:
        raise connectors.ConnectorAuthError(
            "Zoom did not issue an access token — check the Account ID, "
            "Client ID, and Client Secret, and that the app is activated")
    return {"Authorization": f"Bearer {token}"}


def test(creds):
    headers = _bearer(creds)
    me = connectors.get_json(f"{BASE}/users/me", headers=headers)
    who = me.get("email") or me.get("id") or "account"
    return f"connected as {who}"


def list_items(creds, since=None):
    headers = _bearer(creds)
    floor = date.today() - timedelta(days=WINDOW_DAYS * MONTHS_BACK)
    if since:
        try:
            floor = max(floor, date.fromisoformat(str(since)[:10]))
        except ValueError:
            pass
    items, seen = [], set()
    to_d = date.today()
    for _ in range(MONTHS_BACK):
        if to_d < floor:
            break
        from_d = max(floor, to_d - timedelta(days=WINDOW_DAYS - 1))
        token = None
        while True:
            params = {"from": from_d.isoformat(), "to": to_d.isoformat(),
                      "page_size": 300}
            if token:
                params["next_page_token"] = token
            data = connectors.get_json(f"{BASE}/users/me/recordings",
                                       headers=headers, params=params)
            for m in data.get("meetings") or []:
                for f in m.get("recording_files") or []:
                    if (f.get("file_type") or "").upper() != "TRANSCRIPT":
                        continue
                    fid = str(f.get("id") or f"{m.get('uuid')}-transcript")
                    if fid in seen:
                        continue
                    seen.add(fid)
                    items.append({
                        "id": fid,
                        "name": m.get("topic") or "Zoom meeting",
                        "kind": "transcript",
                        "modified": m.get("start_time"),
                        "meta": {
                            "topic": m.get("topic"),
                            "start_time": m.get("start_time"),
                            "host_email": m.get("host_email"),
                            "meeting_id": m.get("id"),
                            "share_url": m.get("share_url"),
                            "download_url": f.get("download_url"),
                            "file_extension": f.get("file_extension"),
                        },
                    })
            token = data.get("next_page_token")
            if not token:
                break
        to_d = from_d - timedelta(days=1)
    return items


def fetch_item(creds, item):
    headers = _bearer(creds)
    meta = item["meta"]
    body = connectors.get_bytes(meta["download_url"], headers=headers)
    title = item["name"]
    stamp = (meta.get("start_time") or "")[:10]
    base = f"{title} ({stamp})" if stamp else title
    ext = ".vtt" if (meta.get("file_extension") or "VTT").upper() == "VTT" else ".txt"
    prov = {
        "service": "zoom", "title": title, "date": meta.get("start_time"),
        "author": meta.get("host_email"), "url": meta.get("share_url"),
        "meeting_id": meta.get("meeting_id"),
    }
    return base + ext, body, prov
