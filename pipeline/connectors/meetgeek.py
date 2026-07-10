"""MeetGeek (meetgeek.ai) — meeting transcripts and summaries, user API key.

Verified against docs.meetgeek.ai (2026-07-10, research_notetakers1.json):
REST with ``Authorization: Bearer`` keys minted on the Integrations > Public
API card. Keys are REGION-SPECIFIC — an EU key fails against the US host —
so the region is a credential field: EU/default -> https://api.meetgeek.ai,
US -> https://api-us.meetgeek.ai. Works on Free (100 requests/day), so this
adapter stays frugal: the list endpoint (id + start/end timestamps only,
limit 500, cursor pagination, no documented date filter — ``since`` applies
client-side) is never followed by per-meeting detail calls; the title and
content cost calls only when an item is actually imported (detail +
paginated transcript + summary fallback). Transcript sentences carry speaker
names and ABSOLUTE ISO timestamps — cues are offset against the meeting's
timestamp_start_utc to make .vtt. Deleted/expired meetings can return 410.
"""

import datetime

import connectors

BASES = {"eu": "https://api.meetgeek.ai", "us": "https://api-us.meetgeek.ai"}

SERVICE = {
    "slug": "meetgeek",
    "name": "MeetGeek",
    "category": "AI Meeting Notetakers",
    "blurb": "Meeting transcripts, summaries, and highlights",
    "fields": [
        {"key": "api_key", "label": "API key", "secret": True},
        {"key": "region", "label": "Data region (EU or US)", "secret": False},
    ],
    "key_steps": [
        "Sign in at app.meetgeek.ai",
        "Go to Integrations and find the Public API card",
        "Generate your API key from that card and paste it here",
        "Enter your data region — EU (the default) or US; keys only work "
        "in the region they were created in",
    ],
    "plan_note": "Works on every MeetGeek plan, including Free "
                 "(100 API requests per day).",
    "docs_url": "https://docs.meetgeek.ai",
}


def _base(creds):
    region = str(creds.get("region") or "eu").strip().lower()
    return BASES.get(region, BASES["eu"])


def _headers(creds):
    return {"Authorization": f"Bearer {creds['api_key'].strip()}"}


def test(creds):
    data = connectors.get_json(f"{_base(creds)}/v1/meetings",
                               headers=_headers(creds), params={"limit": 1})
    n = len(data.get("meetings") or [])
    more = (data.get("pagination") or {}).get("next_cursor")
    return f"connected — {n}{'+' if more else ''} meetings visible"


def list_items(creds, since=None):
    items, cursor = [], None
    while True:
        params = {"limit": 500}
        if cursor:
            params["cursor"] = cursor
        data = connectors.get_json(f"{_base(creds)}/v1/meetings",
                                   headers=_headers(creds), params=params)
        for m in data.get("meetings") or []:
            start = str(m.get("timestamp_start_utc") or "")
            if since and start < str(since):
                continue
            name = (f"MeetGeek meeting {start[:16].replace('T', ' ')}".strip()
                    if start else "MeetGeek meeting")
            items.append({
                "id": str(m.get("meeting_id")),
                "name": name,
                "kind": "transcript",
                "modified": m.get("timestamp_start_utc"),
                "meta": m,
            })
        cursor = (data.get("pagination") or {}).get("next_cursor")
        if not cursor:
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


def fetch_item(creds, item):
    m = item["meta"]
    mid = m.get("meeting_id") or item["id"]
    b = _base(creds)
    detail = connectors.get_json(f"{b}/v1/meetings/{mid}",
                                 headers=_headers(creds))
    title = detail.get("title") or item["name"]
    start = m.get("timestamp_start_utc") or detail.get("timestamp_start_utc")
    stamp = str(start or "")[:10]
    base = f"{title} ({stamp})" if stamp else title
    prov = {"service": "meetgeek", "title": title, "date": start}
    sentences, cursor = [], None
    while True:
        params = {"limit": 500}
        if cursor:
            params["cursor"] = cursor
        page = connectors.get_json(f"{b}/v1/meetings/{mid}/transcript",
                                   headers=_headers(creds), params=params)
        sentences.extend(page.get("sentences") or [])
        cursor = (page.get("pagination") or {}).get("next_cursor")
        if not cursor:
            break
    if sentences:
        prov["speakers"] = sorted({s.get("speaker") for s in sentences
                                   if s.get("speaker")})
        stamps = [_iso(s.get("timestamp")) for s in sentences]
        t0 = _iso(start) or stamps[0]
        try:
            offs = [(t - t0).total_seconds() for t in stamps] \
                if all(stamps) and t0 else None
        except TypeError:
            offs = None
        if offs is not None:
            cues = []
            for i, s in enumerate(sentences):
                end = offs[i + 1] if i + 1 < len(sentences) else offs[i]
                cues.append(f"{_vtt_time(offs[i])} --> {_vtt_time(end)}\n"
                            f"<v {s.get('speaker') or 'Speaker'}>"
                            f"{s.get('transcript') or ''}")
            return (f"{base}.vtt",
                    ("WEBVTT\n\n" + "\n\n".join(cues) + "\n").encode("utf-8"),
                    prov)
        lines = [f"{s.get('speaker') or 'Speaker'}: {s.get('transcript') or ''}"
                 for s in sentences]
        return (f"{base}.txt", "\n".join(lines).encode("utf-8"), prov)
    parts = detail.get("participants") or []
    prov["speakers"] = [(p.get("name") or p.get("email")) if isinstance(p, dict)
                        else str(p) for p in parts]
    data = connectors.get_json(f"{b}/v1/meetings/{mid}/summary",
                               headers=_headers(creds))
    summary = data.get("summary") if isinstance(data, dict) else ""
    return (f"{base} — summary.md",
            f"# {title}\n\n{summary or ''}\n".encode("utf-8"), prov)
