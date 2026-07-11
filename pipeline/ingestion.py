"""M2-1 / G-SC2 — PyMuPDF page-accurate ingestion with per-page OCR routing.

Recovers per-page text with correct 1-based page numbers. Born-digital pages use the
fast PyMuPDF text path; image-only/scanned pages (no text layer) route through the
LOCAL Tesseract engine (D-15, CE_PLAN §8 step 3, SC-2). Text is returned RAW (verbatim,
no normalization) so downstream stages can compute character offsets for mechanical
span-level citation verification (M2-6). OCR is fully local (no network/model fetch).

Scope: page-accurate text extraction + OCR routing only. No chunking, embeddings,
vector DB, reranker, LLM, or HTTP surface.
"""

import os
from pathlib import Path

import fitz  # PyMuPDF

import apppaths

# A page with fewer than this many non-whitespace extractable chars is treated as
# having no real text layer (CE_PLAN §8 step 3).
_MIN_TEXT_LAYER_CHARS = 20
# Fraction of page area covered by images at/above which the page is "image-heavy".
# OCR is applied only when a page has negligible text AND is image-heavy, so a
# sparse-but-digital page (a few words, no full-page image) is NOT misrouted to OCR (T4).
_IMAGE_COVER_THRESHOLD = 0.5
# Mean Tesseract word confidence (0-100) below this is "fail loud": the page is
# flagged ocr_failed and NOT indexed as authoritative text (CE_PLAN §8 failure modes).
_MIN_OCR_CONFIDENCE = 50.0
_OCR_DPI = 300  # render resolution for scanned pages


def configure_tesseract():
    """Point pytesseract at the vendored binary when it exists (frozen app:
    Contents/Resources/pipeline/vendor/tesseract, shipped by B1's
    desktop/vendor_tesseract.sh). Dev machines keep the system tesseract.
    Idempotent; returns the resolved command for logging."""
    vend = apppaths.assets_root() / "vendor" / "tesseract"
    binary = vend / "bin" / "tesseract"
    if binary.is_file():
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = str(binary)
        os.environ["TESSDATA_PREFIX"] = str(vend / "share" / "tessdata")
        return str(binary)
    return "system default"


configure_tesseract()


def extract_pages(pdf_path):
    """Extract text from a born-digital PDF, organized by page.

    Returns a list of dicts (one per physical page, in order):
        {"source_filename": str, "page_number": int (1-based), "page_text": str}
    """
    pdf_path = Path(pdf_path)
    records = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc):
            records.append(
                {
                    "source_filename": pdf_path.name,
                    "page_number": index + 1,  # 1-based, matches the manifest
                    "page_text": page.get_text(),
                }
            )
    return records


def _ocr_verdict(text, confidence, min_confidence=_MIN_OCR_CONFIDENCE):
    """Fail-loud check for an OCR'd page. Returns (failed: bool, reason: str | None).

    A page is failed if OCR yielded no usable text or its mean confidence is below the
    floor — so unreadable scans are flagged, never indexed as authoritative garbage."""
    if not text.strip():
        return True, "empty OCR output (no text recovered)"
    if confidence is not None and confidence < min_confidence:
        return True, f"low OCR confidence {confidence:.1f} < {min_confidence:.0f}"
    return False, None


def _image_coverage(page):
    """Fraction of the page area covered by embedded raster images (capped at 1.0).
    A full-page scan -> ~1.0; a born-digital page with no/small logo -> ~0.0."""
    page_area = abs(page.rect.width * page.rect.height) or 1.0
    area = 0.0
    for info in page.get_image_info():
        bbox = info.get("bbox")
        if bbox:
            area += abs((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    return min(area / page_area, 1.0)


def _merge_text_layer_and_ocr(text_layer, ocr_text):
    """Merge: keep the authoritative text-layer text, then append OCR lines it doesn't
    already contain (normalized line dedup), so embedded-image text isn't lost (T4)."""
    seen = {" ".join(line.split()).lower() for line in text_layer.splitlines() if line.strip()}
    extra = [line for line in ocr_text.splitlines()
             if line.strip() and " ".join(line.split()).lower() not in seen]
    return text_layer + ("\n" + "\n".join(extra) if extra else "")


def _ocr_page(page, dpi=_OCR_DPI):
    """OCR one rendered page with local Tesseract. Returns (page_text, mean_confidence).

    Single Tesseract pass: image_to_data gives both the words (reassembled into lines,
    preserving reading order) and per-word confidence, so page_text and the confidence
    used for the fail-loud check come from the same recognition."""
    import io

    import pytesseract
    from PIL import Image

    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    lines, current, current_key, confs = [], [], None, []
    for word, conf, block, par, line in zip(
        data["text"], data["conf"], data["block_num"], data["par_num"], data["line_num"]
    ):
        if not word.strip():
            continue
        key = (block, par, line)
        if current_key is not None and key != current_key:
            lines.append(" ".join(current))
            current = []
        current.append(word)
        current_key = key
        c = float(conf)
        if c >= 0:  # Tesseract uses -1 for non-text regions
            confs.append(c)
    if current:
        lines.append(" ".join(current))

    text = "\n".join(lines)
    confidence = (sum(confs) / len(confs)) if confs else None
    return text, confidence


def extract_pages_ocr(pdf_path, dpi=_OCR_DPI, min_confidence=_MIN_OCR_CONFIDENCE):
    """Page-accurate extraction with per-page text-vs-image routing (D-15, SC-2).

    Each page keeps the core {source_filename, page_number, page_text} shape so it feeds
    the existing chunk->offset path unchanged, plus routing/quality metadata:
        source: "pymupdf" | "tesseract"
        ocr_failed: bool         (True -> page_text is NOT authoritative)
        ocr_confidence: float | None
        flag_reason: str | None

    Born-digital pages (a real text layer) take the fast PyMuPDF path with byte-identical
    text. Image-only pages route through local Tesseract; empty/low-confidence OCR is
    flagged (fail-loud) rather than indexed as authoritative garbage."""
    pdf_path = Path(pdf_path)
    records = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc):
            digital_text = page.get_text()
            has_text = len(digital_text.strip()) >= _MIN_TEXT_LAYER_CHARS
            image_heavy = _image_coverage(page) >= _IMAGE_COVER_THRESHOLD

            def rec(page_text, source, ocr_failed=False, confidence=None, reason=None):
                return {
                    "source_filename": pdf_path.name, "page_number": index + 1,
                    "page_text": page_text, "source": source, "ocr_failed": ocr_failed,
                    "ocr_confidence": confidence, "flag_reason": reason,
                }

            if has_text and not image_heavy:
                # born-digital: unchanged fast path (byte-identical to extract_pages)
                records.append(rec(digital_text, "pymupdf"))
            elif not has_text and not image_heavy:
                # sparse-but-digital / blank: a real (tiny) or empty text layer with no
                # full-page image -> stay on PyMuPDF, do NOT OCR (T4 misroute fix).
                records.append(rec(digital_text, "pymupdf"))
            elif not has_text and image_heavy:
                # image-only scanned page -> OCR; fail loud on empty/low-confidence.
                text, confidence = _ocr_page(page, dpi=dpi)
                failed, reason = _ocr_verdict(text, confidence, min_confidence=min_confidence)
                records.append(rec("" if failed else text, "tesseract", failed, confidence, reason))
            else:
                # mixed: a real text layer AND a large embedded image -> keep the
                # authoritative text layer and OCR-merge the embedded image text (T4),
                # so embedded-image content isn't lost. Authoritative text present, so
                # the page is not failed even if the OCR add is low-confidence.
                ocr_text, confidence = _ocr_page(page, dpi=dpi)
                merged = _merge_text_layer_and_ocr(digital_text, ocr_text)
                records.append(rec(merged, "mixed", False, confidence, None))
    return records
