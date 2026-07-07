"""Task 3 — async ingest worker: turn an uploaded document into indexed, matter-scoped
chunks in the dedicated .lancedb_kb store, and drive the catalog status lifecycle.

extract (OCR-aware) -> chunk (offset-faithful, so span verification works) -> embed via
loopback bge-m3 -> append into .lancedb_kb (table 'chunks') scoped to the matter slug ->
set status ready / needs_review (any ocr_failed page) / failed (extraction error).
Idempotent: a doc's existing chunks are removed before re-adding, so re-ingest never
duplicates. Writes ONLY to .lancedb_kb — never an eval store.
"""

import re
import shutil
from pathlib import Path

import catalog
import keyvault
from embed_store import add_chunks, delete_doc
from extractors import extract

_CHUNK_CHARS = 900  # target window size; cuts on a nearby newline to avoid mid-line splits

# Section-heading heuristics for uploaded legal documents (Move 1d, D-69): markdown
# headers, numbered clause headings ("4. TERMINATION", "12. Governing Law"),
# ARTICLE/SECTION lines, and short ALL-CAPS heading lines. Deliberately conservative —
# a missed heading only means a plainer breadcrumb; a false positive only adds noise to
# the breadcrumb, never to chunk text/offsets (verification substrate untouched).
_HEADING_RE = re.compile(
    r"^(?:"
    r"#{1,6}\s+(?P<md>.+?)\s*#*"                                   # markdown header
    r"|(?P<num>\d{1,2}\.\s+[A-Z][A-Za-z0-9 ,&'/()-]{2,60})"        # numbered clause
    r"|(?P<art>(?:ARTICLE|SECTION)\s+[\dIVXLC]+[.:]?\s*[A-Za-z0-9 ,&'/()-]{0,60})"
    r"|(?P<caps>[A-Z][A-Z0-9 ,&'/():-]{5,60})"                     # ALL-CAPS line
    r")\s*$", re.M)


def _heading_text(m):
    return next(g for g in (m.group("md"), m.group("num"), m.group("art"),
                            m.group("caps")) if g).strip()


def _chunk_pages(pages, matter_slug, filename, document_type="document"):
    """Section-aware windowing with PAGE-relative offsets, so
    ``page_text[char_start:char_end] == chunk.text`` (the substrate span verification
    needs). Pages with no authoritative text (e.g. ocr_failed -> blanked) yield nothing.

    Move 1d (D-69): chunks now cut at detected section headings (window boundaries never
    cross a heading), carry the section breadcrumb + a real ``document_type`` in both the
    payload and the SAC embedding line (matching the eval chunker's
    ``[Matter | Type | Section]`` format — the scale eval measured the old blind window +
    empty breadcrumb at 81% golden recall@5 vs the richer format's ~98% equivalent).
    Extractor provenance (pymupdf/tesseract/txt) moves to its own ``provenance`` field
    instead of squatting ``document_type``."""
    chunks = []
    section = ""  # persists across pages until the next heading
    for p in pages:
        pt = p["page_text"]
        pno = p["page_number"]
        if not pt.strip():
            continue
        # heading starts on this page, in offset order (page-relative)
        marks = [(m.start(), _heading_text(m)) for m in _HEADING_RE.finditer(pt)]
        bounds = sorted({0, len(pt), *(s for s, _ in marks)})
        head_at = dict(marks)
        for bi in range(len(bounds) - 1):
            seg_start, seg_end = bounds[bi], bounds[bi + 1]
            if seg_start in head_at:
                section = head_at[seg_start]
            i = seg_start
            while i < seg_end:
                end = min(i + _CHUNK_CHARS, seg_end)
                if end < seg_end:
                    nl = pt.find("\n", end)
                    if nl != -1 and nl < seg_end and nl - end < 200:
                        end = nl
                text = pt[i:end]
                if text.strip():
                    chunks.append({
                        "source_filename": filename, "matter": matter_slug,
                        "document_type": document_type,
                        "provenance": p.get("source", "doc"),
                        "page_number": pno, "section": section,
                        "char_start": i, "char_end": end, "text": text,
                        "embedding_text": (f"[Matter: {matter_slug} | Type: "
                                           f"{document_type} | Section: {section}]\n{text}"),
                    })
                i = end
    return chunks


def ingest_document(doc_id, file_path, matter_slug, db_path, catalog_db=None,
                    on_stage=None):
    """Extract -> chunk -> embed -> upsert into .lancedb_kb; update + return the status.

    D-73: a DEK-encrypted native decrypts to a scratch file INSIDE the store
    directory — which in production is the mounted encrypted volume, so extractor
    plaintext never touches the bare SSD. The original filename is preserved in a
    per-doc subdir (chunk metadata + delete_doc scope by name); the scratch tree is
    removed when ingest ends, success or not. Plain natives take the direct path.

    ``on_stage`` (Move 0c): optional callback invoked with the stage name as each phase
    begins ("extract", "embed_write", "tables") — the ingest worker uses it for the Hub
    progress surface and per-stage timing logs. Purely observational; never alters flow."""
    file_path = Path(file_path)
    if not keyvault.is_encrypted_file(file_path):
        return _ingest_inner(doc_id, file_path, matter_slug, db_path, catalog_db, on_stage)
    scratch = Path(db_path) / ".ingest_tmp" / str(doc_id)
    try:
        scratch.mkdir(parents=True, exist_ok=True)
        plain = scratch / file_path.name
        plain.write_bytes(
            keyvault.read_matter_file(file_path, matter_slug, db_path=catalog_db))
        return _ingest_inner(doc_id, plain, matter_slug, db_path, catalog_db, on_stage)
    except keyvault.KeyDestroyedError as e:
        catalog.update_document(doc_id, "failed", str(e), db_path=catalog_db)
        return "failed"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        try:
            scratch.parent.rmdir()  # drop .ingest_tmp itself once no doc is in flight
        except OSError:
            pass


def _ingest_inner(doc_id, file_path, matter_slug, db_path, catalog_db, on_stage):
    def stage(name):
        if on_stage is not None:
            on_stage(name)

    file_path = Path(file_path)
    filename = file_path.name

    # Move 2a (D-70): user-designated transcripts take the line-aware path — clean
    # gutter-stripped page text, a line map saved to the catalog, one chunk per page.
    # A condensed 4-up transcript FAILS LOUD (a confidently wrong page:line is worse
    # than no ingest). The prose path below is unchanged.
    row = catalog.get_document(doc_id, db_path=catalog_db)
    if row and row.get("doc_type") == "transcript":
        return _ingest_transcript(doc_id, file_path, matter_slug, db_path,
                                  catalog_db, stage)

    stage("extract")
    try:
        pages = extract(file_path)
    except Exception as e:  # unreadable / unsupported -> failed (fail loud)
        catalog.update_document(doc_id, "failed", f"{type(e).__name__}: {e}", db_path=catalog_db)
        return "failed"

    needs_review = any(p.get("ocr_failed") for p in pages)
    chunks = _chunk_pages(pages, matter_slug, filename)

    # Idempotent: drop any prior chunks for this (filename, matter) before re-adding.
    stage("embed_write")
    delete_doc(db_path, filename, matter_slug)
    add_chunks(chunks, db_path)

    # T-TBL: additively index any TABLES (Docling path), so fee schedules / damages
    # matrices become span-verifiably citable. The prose path above is UNCHANGED; this
    # runs only on table-bearing PDFs (cheap PyMuPDF pre-check, D-51 latency) and is
    # best-effort — a table-pass failure never fails the prose ingest. Table chunks were
    # cleared by delete_doc above, so re-ingest stays idempotent.
    table_chunks = []
    if file_path.suffix.lower() == ".pdf":
        stage("tables")
        try:
            import table_ingest
            if table_ingest.has_tables(file_path):
                table_chunks = table_ingest.ingest_tables(
                    file_path, matter_slug, db_path, filename=filename)
        except Exception:
            table_chunks = []

    if not chunks and not table_chunks and not needs_review:
        status, reason = "failed", "no extractable text"
    elif needs_review:
        status = "needs_review"
        reason = "low-confidence OCR on one or more pages"
    else:
        status, reason = "ready", None
    catalog.update_document(doc_id, status, reason, db_path=catalog_db)
    return status


def _ingest_transcript(doc_id, file_path, matter_slug, db_path, catalog_db, stage):
    """Move 2a (D-70): the transcript ingest path. Extract with the numbered-gutter
    parser (PDF) or ASCII page/line parser (.txt), persist the line map, chunk one page
    per chunk. Line maps index the CLEAN page text — the same text chunks carry — so
    verified span offsets map straight to line ranges at citation time."""
    import transcript_extract as te

    stage("extract")
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".pdf":
            pages = te.extract_transcript_pdf(file_path)
        elif suffix in (".txt", ".md"):
            pages = te.extract_transcript_txt(file_path)
        else:
            raise ValueError(f"transcripts must be .pdf or .txt (got {suffix}); "
                             "export E-Transcript (.ptx) to PDF or ASCII first")
    except te.CondensedTranscriptError as e:
        catalog.update_document(doc_id, "failed", str(e), db_path=catalog_db)
        return "failed"
    except Exception as e:
        catalog.update_document(doc_id, "failed", f"{type(e).__name__}: {e}",
                                db_path=catalog_db)
        return "failed"

    entries = [(pno, ln, s, e)
               for pno, _clean, line_entries in pages if line_entries
               for ln, s, e in line_entries]
    numbered_pages = sum(1 for _p, _c, le in pages if le)
    chunks = te.chunk_transcript_pages(pages, matter_slug, file_path.name)

    stage("embed_write")
    delete_doc(db_path, file_path.name, matter_slug)
    add_chunks(chunks, db_path)
    catalog.save_line_map(doc_id, entries, db_path=catalog_db)

    if not chunks:
        status, reason = "failed", "no extractable text"
    elif numbered_pages == 0:
        # ingested fine, but nothing looked like a numbered transcript page — honest
        # signal that page:line citations will not be available for this file
        status = "needs_review"
        reason = ("no numbered transcript lines detected - indexed as plain pages "
                  "(page-level citations only)")
    else:
        status, reason = "ready", None
    catalog.update_document(doc_id, status, reason, db_path=catalog_db)
    return status
