"""Avoma (avoma.com) — meeting transcripts and AI notes, admin-created API key.

Verified against dev.avoma.com/openapi.yml + help.avoma.com (2026-07-10,
research_notetakers2.json): REST at https://api.avoma.com, auth
``Authorization: Bearer CLIENT_KEY:CLIENT_SECRET`` where the key string is
created under Settings > Organization > Developer (admin-only — a solo user
who owns their own workspace IS its admin). ``from_date`` and ``to_date`` are
REQUIRED on ``GET /v1/meetings/``, so listing defaults to a five-year window
ending now; the docs state no maximum window, so one window per sync (60
req/min limit) and pagination follows the ``next`` URL. Meetings flag
``transcript_ready`` / ``notes_ready``: ready transcripts come from
``GET /v1/transcriptions/{transcription_uuid}/`` (speaker map + per-utterance
word-timestamp floats -> .vtt) and AI notes from
``GET /v1/notes/?meeting_uuid=...&output_format=json`` (rendered to .md).
"""

import datetime
import json

import connectors

BASE = "https://api.avoma.com"
WINDOW_DAYS = 5 * 365

SERVICE = {
    "slug": "avoma",
    "name": "Avoma",
    "category": "AI Meeting Notetakers",
    "blurb": "Meeting transcripts and AI-generated notes",
    "fields": [{"key": "api_key",
                "label": "API key (CLIENT_KEY:CLIENT_SECRET)", "secret": True}],
    "key_steps": [
        "Log in to Avoma as an administrator (the owner of a solo "
        "workspace is its administrator)",
        "Go to Settings > Organization > Developer",
        "Click Add API Key, give it a name, and pick a User scope "
        "from the dropdown",
        "Click Create, then copy the key string (CLIENT_KEY:CLIENT_SECRET) "
        "right away — it is shown only once — and paste it here",
    ],
    "plan_note": "Requires an Avoma plan with API access "
                 "(Organization or Enterprise).",
    "docs_url": "https://dev.avoma.com/",
}


def _headers(creds):
    return {"Authorization": f"Bearer {creds['api_key'].strip()}"}


def _rfc3339(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test(creds):
    data = connectors.get_json(f"{BASE}/v1/users/", headers=_headers(creds))
    n = data.get("count") if isinstance(data, dict) else len(data or [])
    return f"connected — {n if n is not None else 'workspace'} users visible"


def list_items(creds, since=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    from_date = since or _rfc3339(now - datetime.timedelta(days=WINDOW_DAYS))
    url = f"{BASE}/v1/meetings/"
    params = {"from_date": from_date, "to_date": _rfc3339(now),
              "page_size": 100}
    items = []
    while url:
        data = connectors.get_json(url, headers=_headers(creds), params=params)
        for m in data.get("results") or []:
            row = {"name": m.get("subject") or "Avoma meeting",
                   "modified": m.get("start_at"), "meta": m}
            if m.get("transcript_ready"):
                items.append(dict(row, id=str(m.get("uuid")), kind="transcript"))
            if m.get("notes_ready"):
                items.append(dict(row, id=f"{m.get('uuid')}:notes", kind="note"))
        url, params = data.get("next"), None  # ``next`` is a full URL
    return items


def _vtt_time(seconds):
    """Avoma utterance ``timestamps`` are word-level second floats."""
    ms = max(0, int(round(seconds * 1000)))
    return (f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:"
            f"{ms % 60000 // 1000:02d}.{ms % 1000:03d}")


def _texts(node, out):
    """Pull readable strings out of the notes JSON tree, in document order."""
    if isinstance(node, str):
        if node.strip():
            out.append(node.strip())
    elif isinstance(node, list):
        for n in node:
            _texts(n, out)
    elif isinstance(node, dict):
        for k in ("category", "label", "title", "heading"):
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                out.append(f"## {v.strip()}")
        for k in ("text", "note", "value"):
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
        for k in ("results", "data", "notes", "children", "items", "content"):
            if k in node:
                _texts(node[k], out)


def fetch_item(creds, item):
    m = item["meta"]
    title = item["name"]
    stamp = str(m.get("start_at") or "")[:10]
    base = f"{title} ({stamp})" if stamp else title
    prov = {"service": "avoma", "title": title, "date": m.get("start_at"),
            "author": m.get("organizer_email"), "url": m.get("url")}
    if item["kind"] == "note":
        prov["speakers"] = [a.get("name") or a.get("email")
                            for a in m.get("attendees") or []
                            if isinstance(a, dict)
                            and (a.get("name") or a.get("email"))]
        data = connectors.get_json(f"{BASE}/v1/notes/", headers=_headers(creds),
                                   params={"meeting_uuid": m.get("uuid"),
                                           "output_format": "json"})
        out = []
        _texts(data, out)
        if out:
            return (f"{base} — notes.md",
                    (f"# {title}\n\n" + "\n\n".join(out) + "\n").encode("utf-8"),
                    prov)
        return (f"{base} — notes.json",
                json.dumps(data, indent=2).encode("utf-8"), prov)
    tuid = m.get("transcription_uuid")
    if tuid:
        data = connectors.get_json(f"{BASE}/v1/transcriptions/{tuid}/",
                                   headers=_headers(creds))
    else:
        data = connectors.get_json(f"{BASE}/v1/transcriptions/",
                                   headers=_headers(creds),
                                   params={"meeting_uuid": m.get("uuid")})
    if isinstance(data, list):
        data = data[0] if data else {}
    elif isinstance(data.get("results"), list):
        data = (data["results"] or [{}])[0]
    names = {s.get("id"): s.get("name") for s in data.get("speakers") or []}
    utts = data.get("transcript") or []
    prov["speakers"] = sorted({n for n in names.values() if n})
    cues, t_ok = [], True
    for u in utts:
        ts = [t for t in u.get("timestamps") or []
              if isinstance(t, (int, float))]
        if not ts:
            t_ok = False
            break
        cues.append(f"{_vtt_time(ts[0])} --> {_vtt_time(ts[-1])}\n"
                    f"<v {names.get(u.get('speaker_id')) or 'Speaker'}>"
                    f"{u.get('transcript') or ''}")
    if t_ok and cues:
        return (f"{base}.vtt",
                ("WEBVTT\n\n" + "\n\n".join(cues) + "\n").encode("utf-8"), prov)
    if utts:
        lines = [f"{names.get(u.get('speaker_id')) or 'Speaker'}: "
                 f"{u.get('transcript') or ''}" for u in utts]
        return (f"{base}.txt", "\n".join(lines).encode("utf-8"), prov)
    raise connectors.ConnectorError(
        "the transcript for this meeting is not ready yet — try the import "
        "again after Avoma finishes processing it")
