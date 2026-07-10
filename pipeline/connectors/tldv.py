"""tl;dv (tldv.io) — meeting transcripts and AI notes, user API key.

Verified against doc.tldv.io (2026-07-10, research_notetakers1.json): REST at
https://pasta.tldv.io, auth header ``x-api-key`` (HTTPS required), key
self-served under Settings > Personal settings > API Keys. The API version is
explicitly v1alpha1 — shapes may change before v1. ``GET /v1alpha1/meetings``
pages by ``page`` (response carries page/pages/total and has no documented
date filter, so ``since`` is applied client-side); each meeting yields a
transcript item (``/meetings/{id}/transcript`` -> .vtt from per-utterance
speaker + startTime/endTime seconds) and a notes item (``/meetings/{id}/notes``
-> the ready-made markdownContent as .md). The deprecated /highlights endpoint
is never used. API export requires the meeting ORGANIZER on Pro or higher —
meetings shared by Free-plan organizers stay invisible even to paid users.
"""

import connectors

BASE = "https://pasta.tldv.io/v1alpha1"

SERVICE = {
    "slug": "tldv",
    "name": "tl;dv",
    "category": "AI Meeting Notetakers",
    "blurb": "Meeting recordings, transcripts, and AI notes",
    "fields": [{"key": "api_key", "label": "API key", "secret": True}],
    "key_steps": [
        "Log in at tldv.io",
        "Go to Settings > Personal settings > API Keys",
        "Generate a new API key",
        "Copy the key and paste it here",
    ],
    "plan_note": "Requires tl;dv Pro or higher, and you must be the "
                 "meeting organizer.",
    "docs_url": "https://doc.tldv.io/index.html",
}


def _headers(creds):
    return {"x-api-key": creds["api_key"].strip()}


def test(creds):
    data = connectors.get_json(f"{BASE}/meetings", headers=_headers(creds))
    return f"connected — {data.get('total', 0)} meetings visible"


def list_items(creds, since=None):
    items, page = [], 0
    while True:
        params = {"page": page} if page else None
        data = connectors.get_json(f"{BASE}/meetings", headers=_headers(creds),
                                   params=params)
        for m in data.get("results") or []:
            if since and str(m.get("happenedAt") or "") < str(since):
                continue
            row = {"name": m.get("name") or "tl;dv meeting",
                   "modified": m.get("happenedAt"), "meta": m}
            items.append(dict(row, id=str(m.get("id")), kind="transcript"))
            items.append(dict(row, id=f"{m.get('id')}:notes", kind="note"))
        page = int(data.get("page") or 0) + 1
        if page >= int(data.get("pages") or 1):
            return items


def _vtt_time(seconds):
    """tl;dv utterance startTime/endTime are seconds from meeting start."""
    if not isinstance(seconds, (int, float)):
        return None
    ms = max(0, int(round(seconds * 1000)))
    return (f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:"
            f"{ms % 60000 // 1000:02d}.{ms % 1000:03d}")


def _notes_md(creds, mid, title):
    data = connectors.get_json(f"{BASE}/meetings/{mid}/notes",
                               headers=_headers(creds))
    body = data.get("markdownContent")
    if not body:
        topics = sorted(data.get("topics") or [],
                        key=lambda t: t.get("order") or 0)
        body = "\n\n".join(f"## {t.get('title')}\n\n{t.get('summary') or ''}"
                           for t in topics if t.get("title"))
    if not body:
        body = "\n".join(n.get("text") or ""
                         for n in data.get("structuredNotes") or [])
    return f"# {title}\n\n{body}\n".encode("utf-8")


def fetch_item(creds, item):
    m = item["meta"]
    mid = m.get("id") or str(item["id"]).split(":")[0]
    title = item["name"]
    stamp = str(m.get("happenedAt") or "")[:10]
    base = f"{title} ({stamp})" if stamp else title
    org = m.get("organizer") if isinstance(m.get("organizer"), dict) else {}
    prov = {
        "service": "tldv", "title": title, "date": m.get("happenedAt"),
        "author": org.get("email") or org.get("name"),
        "url": m.get("url"),
    }
    if item["kind"] == "note":
        prov["speakers"] = [i.get("name") for i in m.get("invitees") or []
                            if isinstance(i, dict) and i.get("name")]
        return (f"{base} — notes.md", _notes_md(creds, mid, title), prov)
    data = connectors.get_json(f"{BASE}/meetings/{mid}/transcript",
                               headers=_headers(creds))
    utts = data.get("data") or []
    prov["speakers"] = sorted({u.get("speaker") for u in utts if u.get("speaker")})
    if utts:
        cues, t_ok = [], True
        for u in utts:
            start = _vtt_time(u.get("startTime"))
            if start is None:
                t_ok = False
                break
            end = _vtt_time(u.get("endTime"))
            cues.append(f"{start} --> {end or start}\n"
                        f"<v {u.get('speaker') or 'Speaker'}>{u.get('text') or ''}")
        if t_ok and cues:
            return (f"{base}.vtt",
                    ("WEBVTT\n\n" + "\n\n".join(cues) + "\n").encode("utf-8"), prov)
        lines = [f"{u.get('speaker') or 'Speaker'}: {u.get('text') or ''}"
                 for u in utts]
        return (f"{base}.txt", "\n".join(lines).encode("utf-8"), prov)
    return (f"{base} — notes.md", _notes_md(creds, mid, title), prov)
