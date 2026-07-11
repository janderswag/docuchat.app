"""Emit a 1-page IMAGE-ONLY PDF (rendered text, no text layer) for the smoke
gate's OCR step (B2, council 2026-07-11). Uses PyMuPDF only (already a
pipeline dependency). If the bundle's vendored tesseract is missing or broken,
this document can never reach status=ready — extraction yields no text."""
import sys

import fitz  # PyMuPDF

out = sys.argv[1]
doc = fitz.open()
page = doc.new_page(width=612, height=792)
page.insert_text((72, 200), "SYNTHETIC SCANNED SMOKE PAGE", fontsize=24)
page.insert_text((72, 260), "docuchat OCR gate. Not a real document.", fontsize=16)
page.insert_text((72, 320), "The quick brown fox jumps over the lazy dog.", fontsize=16)
pix = page.get_pixmap(dpi=200)          # rasterize: kills the text layer
img = fitz.open()
ip = img.new_page(width=612, height=792)
ip.insert_image(ip.rect, pixmap=pix)
img.save(out)
print(f"wrote {out}")
