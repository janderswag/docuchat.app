"""Move 2a/2b (D-70) — transcript-aware extraction: line maps, clean text, speakers.

Input: a user-designated transcript (doc_type='transcript' at upload — never
auto-detected), as a born-digital PDF with a numbered left gutter (~25 lines/page) or a
court-reporter ASCII .txt (line-number prefixes; pages split by form-feed or "Page N"
headers).

Output per page: CLEAN page text (gutter stripped, so line numbers stop polluting
embeddings and quotes), a LINE MAP [(line, char_start, char_end)] whose offsets index
the clean text — the exact text chunks slice, so the invariant
``page_text[char_start:char_end] == chunk.text`` carries page:line derivation for free —
and the speaker turns present on the page.

THE TRUST RULE (D-19/D-38 extended): page:line citations are DERIVED by mapping
VERIFIER-CONFIRMED span offsets through the line map. The model never asserts a line
number. If the verified span's text occurs more than once on the page, NO line range is
derived (page-only citation): precise or absent, never approximate.

Condensed ("4-up") PDFs are DETECTED and REJECTED for line derivation — sheet numbers
diverge from transcript pages and a confidently wrong "45:12" is worse than a page cite.
"""

import re

import fitz

# A gutter line: optional space, a 1-2 digit line number, whitespace, then content
# (or an empty numbered line).
_GUTTER_LINE = re.compile(r"^\s{0,6}(\d{1,2})(?:\s+(.*))?$")
# Page markers inside ASCII transcripts.
_ASCII_PAGE = re.compile(r"^\s*(?:Page|PAGE)\s+(\d+)\s*$")
# Speaker-turn shapes (clean text): Q./A., THE WITNESS:, MR./MS./MRS./DR. NAME:,
# and examination markers BY MR. NAME:
_TURN_RE = re.compile(
    r"^(?:(?P<q>Q)\.|(?P<a>A)\."
    r"|(?P<by>BY\s+(?:MR|MS|MRS|DR)\.\s+[A-Z][A-Z'-]+)\s*:"
    r"|(?P<sp>THE\s+(?:WITNESS|COURT)|(?:MR|MS|MRS|DR)\.\s+[A-Z][A-Z'-]+)\s*:)",
    re.M)

MIN_NUMBERED_FRACTION = 0.6   # a real transcript page: most non-blank lines numbered
MAX_LINES_PER_PAGE = 28       # >28 numbered lines on one PDF page => condensed 4-up


class CondensedTranscriptError(ValueError):
    """A condensed/multi-page-per-sheet transcript: line derivation refused (D-70)."""


def _parse_numbered_lines(raw_lines):
    """[(line_no, content)] if these raw lines look like a numbered gutter; else None."""
    parsed, numbered, nonblank = [], 0, 0
    for raw in raw_lines:
        if not raw.strip():
            continue
        nonblank += 1
        m = _GUTTER_LINE.match(raw)
        if m:
            numbered += 1
            parsed.append((int(m.group(1)), (m.group(2) or "").rstrip()))
    if not nonblank or numbered / nonblank < MIN_NUMBERED_FRACTION:
        return None
    return parsed


def _clean_page(parsed):
    """Clean page text + line map from parsed (line_no, content) rows. Line numbers may
    restart mid-list only in condensed sheets — callers guard that. Offsets index the
    CLEAN text; every line (even empty) gets a map entry so ranges stay contiguous."""
    out, entries, pos = [], [], 0
    for line_no, content in parsed:
        start = pos
        out.append(content)
        pos += len(content)
        entries.append((line_no, start, pos))
        pos += 1  # the newline we join with
    return "\n".join(out), entries


def _pdf_visual_lines(page):
    """Reconstruct VISUAL lines from word geometry: words sharing a baseline (y0 binned)
    form one line, ordered by x. This survives PDF producers that emit the gutter
    number and the testimony text as separate text objects — where the plain-text
    extraction splits them into separate lines and the gutter becomes undetectable."""
    words = page.get_text("words")  # (x0, y0, x1, y1, word, block, line, word_no)
    rows = {}
    for w in words:
        rows.setdefault(round(w[1] / 4), []).append(w)
    lines = []
    for key in sorted(rows):
        row = sorted(rows[key], key=lambda w: w[0])
        lines.append(" ".join(w[4] for w in row))
    return lines


def extract_transcript_pdf(path):
    """[(page_number, clean_text, line_entries)] for a gutter-numbered PDF.
    Raises CondensedTranscriptError when a sheet carries more than one transcript page
    (line numbers restarting / >MAX_LINES_PER_PAGE numbered lines)."""
    pages = []
    with fitz.open(str(path)) as doc:
        for pno, page in enumerate(doc, 1):
            raw_lines = _pdf_visual_lines(page)
            parsed = _parse_numbered_lines(raw_lines)
            if parsed is None:
                # not gutter-numbered (cover page, exhibit index...) — keep as prose
                pages.append((pno, page.get_text(), None))
                continue
            nums = [n for n, _ in parsed]
            restarts = sum(1 for i in range(1, len(nums)) if nums[i] <= nums[i - 1])
            if len(nums) > MAX_LINES_PER_PAGE or restarts >= 1:
                raise CondensedTranscriptError(
                    f"sheet {pno} carries {len(nums)} numbered lines"
                    f"{' with line-number restarts' if restarts else ''} — this looks "
                    "like a condensed (multi-page-per-sheet) transcript. Upload the "
                    "full-size transcript to get page:line citations; condensed sheets "
                    "would produce confidently wrong line numbers.")
            clean, entries = _clean_page(parsed)
            pages.append((pno, clean, entries))
    return pages


def extract_transcript_txt(path):
    """[(page_number, clean_text, line_entries)] for an ASCII transcript. Pages split on
    form-feed or "Page N" header lines; each page's numbered lines are parsed like the
    PDF gutter. Unnumbered pages ride through as prose with page numbers intact."""
    text = path.read_text(encoding="utf-8", errors="replace")
    # split into (page_number, raw_lines)
    raw_pages = []
    if "\f" in text:
        for i, blk in enumerate(text.split("\f"), 1):
            raw_pages.append((i, blk.splitlines()))
    else:
        cur_no, cur = 1, []
        seen_header = False
        for raw in text.splitlines():
            m = _ASCII_PAGE.match(raw)
            if m:
                if cur and any(l.strip() for l in cur):
                    raw_pages.append((cur_no, cur))
                cur_no, cur, seen_header = int(m.group(1)), [], True
            else:
                cur.append(raw)
        raw_pages.append((cur_no, cur))
        if not seen_header:
            # no page structure at all: treat the whole file as page 1
            raw_pages = [(1, text.splitlines())]
    pages = []
    for pno, raw_lines in raw_pages:
        parsed = _parse_numbered_lines(raw_lines)
        if parsed is None:
            pages.append((pno, "\n".join(raw_lines), None))
        else:
            clean, entries = _clean_page(parsed)
            pages.append((pno, clean, entries))
    return pages


def page_speakers(clean_text):
    """Speaker labels appearing on the page (for embedding/context metadata ONLY —
    display never attributes a quote to a speaker the parser guessed)."""
    speakers = []
    for m in _TURN_RE.finditer(clean_text):
        label = ("Q" if m.group("q") else "A" if m.group("a")
                 else (m.group("by") or m.group("sp")).title())
        if label not in speakers:
            speakers.append(label)
    return speakers


def chunk_transcript_pages(pages, matter_slug, filename):
    """One chunk per transcript page (the retrieval unit — ~25 lines never splits a Q
    from its A within the page, Move 2b). The offset invariant holds against the CLEAN
    page text. The prior page's tail rides along in embedding_text ONLY (cross-page
    exchanges retrievable; never part of citable text). Speaker labels enrich the
    embedding, never the citation."""
    chunks = []
    prev_tail = ""
    for pno, clean, entries in pages:
        if not clean.strip():
            continue
        speakers = page_speakers(clean) if entries else []
        speaker_note = f" | Speakers: {', '.join(speakers)}" if speakers else ""
        context = f"(previous page ends: …{prev_tail})\n" if prev_tail else ""
        chunks.append({
            "source_filename": filename, "matter": matter_slug,
            "document_type": "transcript", "provenance": "transcript",
            "page_number": pno, "section": "",
            "char_start": 0, "char_end": len(clean), "text": clean,
            "embedding_text": (f"[Matter: {matter_slug} | Type: transcript"
                               f"{speaker_note} | Page: {pno}]\n{context}{clean}"),
        })
        prev_tail = clean[-160:].replace("\n", " ")
    return chunks


def derive_lines(page_line_entries, span_start, span_end, page_text, span_text):
    """Map a VERIFIER-CONFIRMED span (page-relative offsets) to a line range string
    like "12-18" (or "12"). Returns None — page-only citation — when the span text
    occurs more than once on the page (the 'Yes.' ambiguity: precise or absent)."""
    if not page_line_entries or span_end <= span_start:
        return None
    norm = " ".join(span_text.split()).casefold()
    hay = " ".join(page_text.split()).casefold()
    if norm and hay.count(norm) > 1:
        return None  # ambiguous on this page — never guess a line
    lines = [ln for ln, s, e in page_line_entries if s < span_end and e > span_start]
    if not lines:
        return None
    lo, hi = min(lines), max(lines)
    return f"{lo}" if lo == hi else f"{lo}-{hi}"
