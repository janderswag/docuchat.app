"""Contract Review router — the clause checklist over the matter's KB documents.

GET /clauses/taxonomy serves the curated checklist (so the UI can show the clauses it
will check). POST /clauses/review {matter, doc_id?} runs extract_clauses over the matter
(scoped to the dedicated .lancedb_kb KB store, read-only) and returns the structured
result. Read-only: there are NO action verbs and no document is mutated (D-2). The matter
is validated against the catalog allowlist (D-35) before answering. Each verified,
chunk-derived citation (D-19/D-38) is enriched with its catalog doc_id so the UI can reuse
the existing /kb/highlight page-thumbnail + cited-span surface. We never add a
model-asserted page — displayed citations stay exactly the verifier's output.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import catalog
import routes_kb  # shared KB store path (monkeypatchable in tests)
from clauses import extract_clauses, load_taxonomy

router = APIRouter()


class ReviewRequest(BaseModel):
    matter: str
    doc_id: int | None = None  # optional: narrow the checklist to one document


@router.get("/clauses/taxonomy")
def taxonomy():
    """The curated clause checklist (ids/names/categories/questions) — no document data."""
    return {"clauses": load_taxonomy()}


@router.post("/clauses/review")
def review(body: ReviewRequest):
    """Run the clause checklist for ``matter`` over its KB documents (read-only)."""
    if not catalog.get_matter(body.matter):
        raise HTTPException(status_code=400, detail=f"unknown matter: {body.matter!r}")

    try:
        out = extract_clauses(body.matter, doc_id=body.doc_id,
                              db_path=str(routes_kb.KB_DB))
    except ValueError as e:
        # unknown doc_id, or the matter has no indexed chunks -> a clean 400
        raise HTTPException(status_code=400, detail=str(e))

    # Enrich each verified citation with its catalog doc_id (by matter+filename) so the
    # UI can request /kb/highlight/<doc_id>. The displayed page/span stay chunk-derived
    # (D-38); we add no model-asserted data.
    by_name = {d["filename"]: d["id"] for d in catalog.list_documents(body.matter)}
    for row in out["results"]:
        for c in row["citations"]:
            c["doc_id"] = by_name.get(c["filename"])
    return out
