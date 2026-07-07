"""Task 5 — visual retrieval evidence (PyMuPDF). Render a retrieved page to a PNG
thumbnail, and highlight the exact cited span on the page (located via page.search_for).

All operations are READ-ONLY on disk: the managed PDF is opened, optionally annotated
IN MEMORY, rendered to PNG, and closed WITHOUT save — the file is never modified.
"""

import fitz


def _open(pdf):
    """fitz-open a path, or in-memory PDF bytes (D-73: decrypted natives are passed
    as bytes so plaintext never touches disk on the view path)."""
    if isinstance(pdf, (bytes, bytearray)):
        return fitz.open(stream=pdf, filetype="pdf")
    return fitz.open(pdf)


def render_page_png(pdf_path, page_number, dpi=110):
    """Render page ``page_number`` (1-based) of ``pdf_path`` to PNG bytes."""
    with _open(pdf_path) as doc:
        page = doc[max(0, page_number - 1)]
        return page.get_pixmap(dpi=dpi).tobytes("png")


def _locate(page, span_text):
    """Rects for ``span_text`` on ``page`` via search_for, with a short-prefix fallback
    (PyMuPDF can't match a long multi-line span verbatim)."""
    if not span_text or not span_text.strip():
        return []
    rects = page.search_for(span_text)
    if not rects:
        words = span_text.split()
        if len(words) > 6:
            rects = page.search_for(" ".join(words[:6]))
    return rects


def find_span_rects(pdf_path, page_number, span_text):
    """Return the fitz.Rect locations of ``span_text`` on the page (possibly empty)."""
    with _open(pdf_path) as doc:
        return _locate(doc[max(0, page_number - 1)], span_text)


def highlight_span_png(pdf_path, page_number, span_text, dpi=150):
    """Render the page with the cited span highlighted. If the span isn't found, render
    the plain page (graceful). Never saves — the managed file is untouched on disk."""
    with _open(pdf_path) as doc:
        page = doc[max(0, page_number - 1)]
        for rect in _locate(page, span_text):
            annot = page.add_highlight_annot(rect)  # in-memory only
            annot.update()
        return page.get_pixmap(dpi=dpi).tobytes("png")
