"""G-SC2 — synthetic scanned-corpus builder. Rasterizes born-digital synthetic PDFs to
image-only PDFs (no text layer) so the OCR path (SC-2) can be exercised against KNOWN
source text. Output goes to the git-ignored documents/synthetic_corpus/scanned/ (D-28).
Synthetic/public docs only — these are renders of the existing fake corpus.

This is a LOCAL build tool (PyMuPDF render only); it pulls no network and writes no
real data. It is NOT part of the serving path and is not imported by the API.
"""

import sys
from pathlib import Path

import fitz  # PyMuPDF

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent
PDF_DIR = REPO_ROOT / "documents" / "synthetic_corpus" / "pdf"
SCANNED_DIR = REPO_ROOT / "documents" / "synthetic_corpus" / "scanned"


def rasterize_to_image_pdf(src_pdf, dst_pdf, dpi=300):
    """Render each page of a born-digital PDF to a raster image and assemble an
    image-only PDF (NO text layer) — a synthetic 'scanned' document. Page size and
    order are preserved. Returns the page count."""
    src_pdf, dst_pdf = Path(src_pdf), Path(dst_pdf)
    with fitz.open(src_pdf) as src, fitz.open() as out:
        for page in src:
            pix = page.get_pixmap(dpi=dpi)
            w_pt, h_pt = pix.width * 72.0 / dpi, pix.height * 72.0 / dpi  # px -> points
            opage = out.new_page(width=w_pt, height=h_pt)
            opage.insert_image(fitz.Rect(0, 0, w_pt, h_pt), stream=pix.tobytes("png"))
        out.save(dst_pdf)
        return src.page_count


def build(dpi=300, limit=None):
    """Rasterize the corpus PDFs into SCANNED_DIR. Returns [(filename, pages), ...]."""
    SCANNED_DIR.mkdir(parents=True, exist_ok=True)
    srcs = sorted(PDF_DIR.glob("*.pdf"))
    if limit is not None:
        srcs = srcs[:limit]
    built = []
    for src in srcs:
        pages = rasterize_to_image_pdf(src, SCANNED_DIR / src.name, dpi=dpi)
        built.append((src.name, pages))
    return built


if __name__ == "__main__":
    dpi = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    for name, pages in build(dpi=dpi):
        print(f"rasterized {name} ({pages} pages) -> {SCANNED_DIR}/{name}")
