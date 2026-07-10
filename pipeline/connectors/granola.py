"""Granola (granola.ai) — AI meeting notes and transcripts, user API key.

Verified against docs.granola.ai (2026-07-10, research_notetakers1.json):
REST at https://public-api.granola.ai/v1, auth ``Authorization: Bearer`` with
a ``grn_``-prefixed key created in the DESKTOP app (Settings > Connectors >
API keys), Business plan and up. ``GET /v1/notes`` pages by
``hasMore``/``cursor`` (``created_after`` filters) and carries the AI summary
inline, so the notes .md costs no extra call (kind to the 5 req/s sustained
limit); ``GET /v1/notes/{id}?include=transcript`` embeds the transcript. The
API only returns notes that already have BOTH a summary and a transcript, so
every note yields a notes item (.md) and a transcript item (.vtt when the
segments carry parseable timestamps, .txt speaker lines otherwise). Key
scopes matter: a Personal-notes key cannot see workspace notes and vice versa.
"""

import datetime

import connectors

BASE = "https://public-api.granola.ai/v1"

SERVICE = {
    "slug": "granola",
    "name": "Granola",
    "category": "AI Meeting Notetakers",
    "blurb": "AI meeting notes and transcripts",
    "fields": [{"key": "api_key", "label": "API key", "secret": True}],
    "key_steps": [
        "Open the Granola desktop app (keys are created there, not on the web)",
        "Go to Settings > Connectors > API keys",
        "Click Create new key and pick the scopes to share "
        "(Personal notes and/or Public notes)",
        "Copy the key — it is shown only once — and paste it here",
    ],
    "plan_note": "Requires the Granola Business plan or higher.",
    "docs_url": "https://docs.granola.ai/introduction",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['api_key'].strip()}"}


def test(creds):
    data = connectors.get_json(f"{BASE}/notes", headers=_headers(creds),
                               params={"limit": 1})
    n = len(data.get("notes") or [])
    return f"connected — {n}{'+' if data.get('hasMore') else ''} notes visible"


def list_items(creds, since=None):
    items, cursor = [], None
    while True:
        params = {}
        if cursor:
            params["cursor"] = cursor
        if since:
            params["created_after"] = since
        data = connectors.get_json(f"{BASE}/notes", headers=_headers(creds),
                                   params=params)
        for n in data.get("notes") or []:
            nid = str(n.get("id"))
            row = {"name": n.get("title") or "Granola note",
                   "modified": n.get("created_at"), "meta": n}
            items.append(dict(row, id=f"{nid}:notes", kind="note"))
            items.append(dict(row, id=nid, kind="transcript"))
        cursor = data.get("cursor")
        if not data.get("hasMore") or not cursor:
            return items


def _iso(ts):
    try:
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _vtt_time(seconds):
    ms = max(0, int(round(seconds * 1000)))
    return (f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:"
            f"{ms % 60000 // 1000:02d}.{ms % 1000:03d}")


def _speaker(seg):
    return seg.get("speaker") or seg.get("source")


def fetch_item(creds, item):
    n = item["meta"]
    title = item["name"]
    stamp = str(n.get("created_at") or "")[:10]
    base = f"{title} ({stamp})" if stamp else title
    owner = n.get("owner")
    prov = {
        "service": "granola", "title": title, "date": n.get("created_at"),
        "author": (owner.get("email") or owner.get("name"))
                  if isinstance(owner, dict) else owner,
    }
    if item["kind"] == "note":
        return (f"{base} — notes.md",
                f"# {title}\n\n{n.get('summary') or ''}\n".encode("utf-8"), prov)
    data = connectors.get_json(f"{BASE}/notes/{n['id']}", headers=_headers(creds),
                               params={"include": "transcript"})
    segs = data.get("transcript") or []
    prov["speakers"] = sorted({_speaker(s) for s in segs if _speaker(s)})
    starts = [_iso(s.get("start_timestamp") or s.get("timestamp")) for s in segs]
    try:
        offs = [(t - starts[0]).total_seconds() for t in starts] \
            if segs and all(starts) else None
    except TypeError:
        offs = None
    if offs is not None:
        cues = []
        for i, s in enumerate(segs):
            end = offs[i + 1] if i + 1 < len(segs) else offs[i]
            cues.append(f"{_vtt_time(offs[i])} --> {_vtt_time(end)}\n"
                        f"<v {_speaker(s) or 'Speaker'}>{s.get('text') or ''}")
        return (f"{base}.vtt",
                ("WEBVTT\n\n" + "\n\n".join(cues) + "\n").encode("utf-8"), prov)
    if segs:
        lines = [f"{_speaker(s) or 'Speaker'}: {s.get('text') or ''}" for s in segs]
        return (f"{base}.txt", "\n".join(lines).encode("utf-8"), prov)
    summary = data.get("summary") or n.get("summary") or ""
    return (f"{base} — notes.md",
            f"# {title}\n\n{summary}\n".encode("utf-8"), prov)
