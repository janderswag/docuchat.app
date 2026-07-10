"""Nextcloud — files over WebDAV with a user-minted app password.

Verified against docs.nextcloud.com (2026-07-10, research_storage.json): any
Nextcloud user can create an app password under Personal settings > Security
> Devices & sessions and use it as HTTP Basic auth against the WebDAV
endpoint ``remote.php/dav/files/{username}/``. With two-factor auth enabled,
app passwords are the ONLY way in — the login password is refused.

Listing walks the chosen folder with Depth-1 PROPFIND per directory (many
servers disable Depth: infinity, and PROPFIND has no pagination), bounded to
2000 entries per pass. An empty-body PROPFIND is an allprop request per RFC
4918, which returns resourcetype/getlastmodified/getcontentlength — enough
here, and it keeps every call inside connectors.request (which treats the
207 Multi-Status reply as the success it is). Downloads are a plain GET of
the file path.
"""

import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote, urlsplit

import connectors

_DAV = "{DAV:}"
MAX_ENTRIES = 2000          # per-pass bound on the folder walk

# Filename extensions docuchat can ingest — the walk keeps only these files.
_DOC_EXTS = (".pdf", ".docx", ".txt", ".md", ".eml", ".html", ".htm",
             ".vtt", ".srt", ".csv", ".json")

SERVICE = {
    "slug": "nextcloud",
    "name": "Nextcloud",
    "category": "Cloud Storage",
    "blurb": "Files from your self-hosted or hosted Nextcloud",
    "fields": [
        {"key": "server_url", "label": "Server URL (https://cloud.example.com)"},
        {"key": "username", "label": "Username"},
        {"key": "app_password", "label": "App password", "secret": True},
        {"key": "folder", "label": "Folder to import", "default": "/"},
    ],
    "key_steps": [
        "Log in to your Nextcloud web interface and click your avatar > "
        "Personal settings",
        "Open the Security section and scroll to Devices & sessions",
        "At the bottom, enter an app name (e.g. 'docuchat') and click "
        "Create new app password",
        "Copy the password immediately — Nextcloud shows it only once",
        "Enter your server URL, username, and the app password here "
        "(and optionally a folder to import)",
    ],
    "plan_note": "Works on any Nextcloud, self-hosted or hosted. If your "
                 "account password lives in an external directory and "
                 "changes, app passwords stop working until you log in to "
                 "the web interface again.",
    "docs_url": "https://docs.nextcloud.com/server/latest/user_manual/en/"
                "session_management.html",
}


def _auth(creds):
    return (creds["username"].strip(), creds["app_password"].strip())


def _dav_root(creds):
    base = creds["server_url"].strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return f"{base}/remote.php/dav/files/{quote(creds['username'].strip())}"


def _norm_folder(creds):
    folder = "/" + (creds.get("folder") or "/").strip().strip("/")
    return folder if folder == "/" else folder + "/"


def _quote_path(path):
    return quote(path, safe="/")


def _rel_path(href, username):
    """Server href (percent-encoded, may include a subpath) -> user path."""
    path = unquote(urlsplit(href).path)
    marker = f"/remote.php/dav/files/{username}"
    i = path.find(marker)
    if i < 0:
        return None
    return path[i + len(marker):] or "/"


def _parse_multistatus(body):
    """Multistatus XML -> [(path-less href, is_dir, getlastmodified)]."""
    try:
        tree = ET.fromstring(body)
    except ET.ParseError:
        raise connectors.ConnectorUnavailable(
            "the Nextcloud server returned an unreadable folder listing")
    out = []
    for resp in tree.iter(f"{_DAV}response"):
        href = resp.findtext(f"{_DAV}href")
        if not href:
            continue
        is_dir = resp.find(f".//{_DAV}resourcetype/{_DAV}collection") is not None
        lastmod = resp.findtext(f".//{_DAV}getlastmodified")
        out.append((href, is_dir, lastmod))
    return out


def _propfind(creds, path, depth):
    # Empty body = allprop; 207 Multi-Status is a 2xx, so request() returns it.
    return connectors.request("PROPFIND", _dav_root(creds) + _quote_path(path),
                              headers={"Depth": str(depth)},
                              auth=_auth(creds))


def test(creds):
    _propfind(creds, "/", 0)
    host = urlsplit(_dav_root(creds)).netloc
    return f"{creds['username'].strip()} @ {host}"


def list_items(creds, since=None):
    username = creds["username"].strip()
    items, seen_entries = [], 0
    queue = [_norm_folder(creds)]
    while queue and seen_entries < MAX_ENTRIES:
        folder = queue.pop(0)
        resp = _propfind(creds, folder, 1)
        for href, is_dir, lastmod in _parse_multistatus(resp.content):
            rel = _rel_path(href, username)
            if rel is None or rel.rstrip("/") == folder.rstrip("/"):
                continue                      # the folder itself, echoed back
            seen_entries += 1
            if seen_entries > MAX_ENTRIES:
                break
            if is_dir:
                queue.append(rel if rel.endswith("/") else rel + "/")
                continue
            name = rel.rsplit("/", 1)[-1]
            if not name.lower().endswith(_DOC_EXTS):
                continue
            items.append({
                "id": rel,
                "name": name,
                "kind": "file",
                "modified": lastmod,
                "meta": {"path": rel, "getlastmodified": lastmod},
            })
    return items


def fetch_item(creds, item):
    meta = item.get("meta") or {}
    path = meta.get("path") or item["id"]
    body = connectors.get_bytes(_dav_root(creds) + _quote_path(path),
                                auth=_auth(creds))
    name = path.rsplit("/", 1)[-1]
    prov = {
        "service": "nextcloud",
        "title": name,
        "path": path,
        "date": meta.get("getlastmodified"),
    }
    return name, body, prov
