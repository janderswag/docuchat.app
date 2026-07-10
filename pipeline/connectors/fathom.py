"""Fathom (fathom.video) — meeting transcripts and summaries, user API key.

Verified against developers.fathom.ai (2026-07-10, research_notetakers1.json):
REST at https://api.fathom.ai/external/v1, auth header ``X-Api-Key`` (NOT
Bearer), key self-served in User Settings > API Access on every plan
including Free. ``GET /meetings?include_transcript=true`` embeds the
transcript per meeting (one call, kind to the 60/min limit); transcripts
render to .vtt (speakers + timestamps kept -> page:line citations), with the
meeting summary as a .md fallback when a transcript is missing. Never send
``destination_url`` — that flips the API into async webhook delivery.
"""

import connectors

BASE = "https://api.fathom.ai/external/v1"

SERVICE = {
    "slug": "fathom",
    "name": "Fathom",
    "category": "AI Meeting Notetakers",
    "blurb": "Call transcripts and meeting summaries",
    "fields": [{"key": "api_key", "label": "API key", "secret": True}],
    "key_steps": [
        "Sign in at fathom.video",
        "Open User Settings and go to the API Access section",
        "Click Generate API Key",
        "Copy the key and paste it here",
    ],
    "plan_note": "Works on every Fathom plan, including Free.",
    "docs_url": "https://developers.fathom.ai/quickstart",
}


def _headers(creds):
    return {"X-Api-Key": creds["api_key"].strip()}


def test(creds):
    data = connectors.get_json(f"{BASE}/meetings", headers=_headers(creds),
                               params={"include_transcript": "false"})
    n = len(data.get("items") or [])
    return f"connected — {n}{'+' if data.get('next_cursor') else ''} meetings visible"


def list_items(creds, since=None):
    items, cursor = [], None
    while True:
        params = {"include_transcript": "true"}
        if cursor:
            params["cursor"] = cursor
        if since:
            params["created_after"] = since
        data = connectors.get_json(f"{BASE}/meetings", headers=_headers(creds),
                                   params=params)
        for m in data.get("items") or []:
            rid = (m.get("recording_id") or m.get("id")
                   or m.get("share_url") or m.get("created_at"))
            items.append({
                "id": str(rid),
                "name": m.get("title") or "Fathom meeting",
                "kind": "transcript" if m.get("transcript") else "summary",
                "modified": m.get("created_at"),
                "meta": m,
            })
        cursor = data.get("next_cursor")
        if not cursor:
            return items


def _vtt_time(ts):
    """Fathom utterance timestamps ('01:23' / '1:02:03' / seconds) -> VTT clock."""
    if isinstance(ts, (int, float)):
        s = int(ts)
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}.000"
    parts = str(ts or "").split(":")
    if not all(p.strip().isdigit() for p in parts) or not parts[0].strip():
        return None
    parts = [int(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0)
    return f"{parts[0]:02d}:{parts[1]:02d}:{parts[2]:02d}.000"


def fetch_item(creds, item):
    m = item["meta"]
    title = item["name"]
    stamp = (m.get("created_at") or "")[:10]
    prov = {
        "service": "fathom", "title": title, "date": m.get("created_at"),
        "author": (m.get("recorded_by") or {}).get("email")
                  if isinstance(m.get("recorded_by"), dict) else m.get("recorded_by"),
        "url": m.get("share_url") or m.get("meeting_url"),
        "speakers": sorted({u.get("speaker") for u in m.get("transcript") or []
                            if u.get("speaker")}),
    }
    base = f"{title} ({stamp})" if stamp else title
    utterances = m.get("transcript") or []
    if utterances:
        cues, t_ok = [], True
        for i, u in enumerate(utterances):
            start = _vtt_time(u.get("timestamp"))
            if start is None:
                t_ok = False
                break
            end = _vtt_time(utterances[i + 1].get("timestamp")) \
                if i + 1 < len(utterances) else start
            cues.append(f"{start} --> {end or start}\n"
                        f"<v {u.get('speaker') or 'Speaker'}>{u.get('text') or ''}")
        if t_ok and cues:
            return (f"{base}.vtt",
                    ("WEBVTT\n\n" + "\n\n".join(cues) + "\n").encode("utf-8"), prov)
        lines = [f"{u.get('speaker') or 'Speaker'}: {u.get('text') or ''}"
                 for u in utterances]
        return (f"{base}.txt", "\n".join(lines).encode("utf-8"), prov)
    summary = m.get("default_summary") or ""
    return (f"{base} — summary.md",
            f"# {title}\n\n{summary}\n".encode("utf-8"), prov)
