"""Move 1c (D-69) — GET /search: retrieval-only search over the KB. No generation, so
zero hallucination surface; every result is a real chunk with filename + page (+
section/doc-type where the store carries them).

Modes:
  mentions (default) — EXHAUSTIVE: every chunk in the (matter-pre-filtered) store whose
      text contains the query, normalized (casefold + collapsed whitespace). This is the
      "find every mention" review workflow the QA endpoints structurally cannot serve.
      Paginated; the response always carries the TRUE total so truncation is labeled
      ("first N of M"), never silent.
  fts — BM25-ranked full-text results (LanceDB native FTS). The index is rebuilt when
      the table version has changed since the last build (the native index does not
      cover rows appended after it was created — the D-66 staleness footgun).

The matter value is validated against the store allowlist exactly like retrieval
(D-35); matter=None is an explicit search-all. Loopback-only, read-only.
"""

import html
import re

from fastapi import APIRouter, HTTPException

import catalog
import routes_kb
from retrieval import _matter_filter, _store_matters
from embed_store import open_table

router = APIRouter()

MAX_LIMIT = 100
_WS = re.compile(r"\s+")
_QUOTES = "\"'“”‘’"   # the verifier's quote class (verifier._QUOTES)
# FTS index freshness: db key -> table version the index was built against.
_FTS_BUILT = {}


def _norm(s):
    """Match under the SAME character contract as the citation verifier
    (verifier._norm_map, minus offset tracking): decode HTML entities, join
    hyphen-linebreaks, drop quote characters and their escapes, collapse
    whitespace, casefold. Without the quote/entity/hyphen steps, a verified
    citation span with straight quotes 0-hits a curly-quoted PDF here — the
    answer would cite a passage Every mention says does not exist (council
    2026-07-11 Move 5 review, finding 1)."""
    s = html.unescape(s)
    s = s.replace('\\"', '"').replace("\\'", "'")
    s = s.replace("-\n", "-")
    s = "".join(ch for ch in s if ch not in _QUOTES)
    return _WS.sub(" ", s).casefold()


def _fresh_fts(table, key):
    version = table.version
    if _FTS_BUILT.get(key) != version:
        table.create_fts_index("text", replace=True)
        _FTS_BUILT[key] = version


def _doc_ids(rows, matter):
    """Attach catalog doc ids so the UI can link the source/highlight viewers.
    Display metadata only — never page/span provenance (those stay chunk-derived)."""
    by_name = {}
    for d in catalog.list_documents(matter):
        by_name[(d["filename"], d["matter_slug"])] = d["id"]
    for r in rows:
        r["doc_id"] = by_name.get((r["source_filename"], r["matter"]))


def _payload(r, q_norm=None):
    text = r["text"]
    snippet_at = 0
    if q_norm:
        pos = _norm(text).find(q_norm)
        # normalized offset ~= raw offset here only for display centering; snippets are
        # display-only (the chunk text itself is the ground truth)
        snippet_at = max(0, pos - 80) if pos >= 0 else 0
    return {
        "source_filename": r["source_filename"], "matter": r["matter"],
        "page_number": r["page_number"], "section": r.get("section", ""),
        "document_type": r.get("document_type", ""),
        "snippet": text[snippet_at:snippet_at + 240],
        "char_start": r["char_start"], "char_end": r["char_end"],
    }


@router.get("/search")
def search(q: str, matter: str | None = None, mode: str = "mentions",
           doc_type: str | None = None, limit: int = 25, offset: int = 0):
    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="empty query")
    if mode not in ("mentions", "fts"):
        raise HTTPException(status_code=400, detail=f"unknown mode: {mode!r}")
    limit = max(1, min(int(limit), MAX_LIMIT))
    offset = max(0, int(offset))

    key = str(routes_kb.KB_DB)
    try:
        table = open_table(key)
    except Exception:
        return {"total": 0, "offset": offset, "limit": limit, "results": [],
                "truncated": False}
    try:
        filt = _matter_filter(table, matter, key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if mode == "fts":
        _fresh_fts(table, key)
        search_q = table.search(q, query_type="fts")
        if filt:
            search_q = search_q.where(filt, prefilter=True)
        rows = search_q.limit(offset + limit).to_arrow().to_pylist()
        if doc_type:
            rows = [r for r in rows if r.get("document_type") == doc_type]
        page = rows[offset:offset + limit]
        out = [_payload(r) for r in page]
        _doc_ids(out, matter)
        # BM25 has no cheap exact total; report what is known honestly
        return {"total": None, "offset": offset, "limit": limit, "results": out,
                "truncated": len(rows) == offset + limit,
                "note": "ranked results; total not computed in fts mode"}

    # mentions: exhaustive normalized-substring scan over the (pre-filtered) chunks
    n = table.count_rows()
    scan = table.search().select(
        ["source_filename", "matter", "page_number", "section", "document_type",
         "char_start", "char_end", "text"])
    if filt:
        scan = scan.where(filt, prefilter=True)
    rows = scan.limit(max(n, 1)).to_arrow().to_pylist()
    q_norm = _norm(q)
    hits = [r for r in rows if q_norm in _norm(r["text"])]
    if doc_type:
        hits = [h for h in hits if h.get("document_type") == doc_type]
    hits.sort(key=lambda r: (r["source_filename"], r["page_number"], r["char_start"]))
    total = len(hits)
    page = hits[offset:offset + limit]
    out = [_payload(r, q_norm) for r in page]
    _doc_ids(out, matter)
    return {"total": total, "offset": offset, "limit": limit, "results": out,
            "truncated": offset + len(out) < total}
