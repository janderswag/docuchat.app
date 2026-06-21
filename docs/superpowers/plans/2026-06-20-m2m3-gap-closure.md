# M2/M3 Acceptance-Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **In this project the plan is executed through the Planner→Builder→Reviewer→Tester relay** — each Task below is one Builder turn; the Planner emits it as a Builder prompt, the Reviewer audits, the Tester independently confirms, and the Planner records the result before the next Task.

**Goal:** Turn every yellow/red on the CE_PLAN §2 SC scorecard green so the system meets the "GO for attorney demo" gate, without disturbing the proven citation-grade capability (M2-8 = FINAL PASS, D-40) or the live eval store.

**Architecture:** The pipeline is already PyMuPDF/Tesseract ingest → chunk+SAC → LanceDB → matter-pre-filtered retrieval → grounded `qwen3:14b` answering → mechanical span verification, over a loopback FastAPI surface. This plan adds, around that spine: (1) a multi-format, idempotent, fail-loud ingestion *orchestrator* (§8); (2) a 20–50 doc synthetic corpus; (3) end-to-end OCR integration (OCR pages become retrievable); (4) OCR robustness (degraded scans + routing fixes) to harden SC-2 short of real data; (5) hybrid dense+BM25 retrieval; (6) first-token latency instrumentation; (7) a scripted redeploy + restore drill. Everything stays local, loopback-only, synthetic-only.

**Tech Stack:** Python 3.12 (`pipeline/.venv`), PyMuPDF (`fitz`), Tesseract (`pytesseract` 0.3.13 → system tesseract 5.5.2), Pillow (degraded-scan synthesis), Docling (offline), LanceDB (embedded), Ollama (`qwen3:14b` + `bge-m3`, loopback), FastAPI/uvicorn, Docker Compose. Tests use `unittest` (NOT pytest).

## Chart → Task map (every yellow/red is owned)

| CE_PLAN M2/M3 item (chart) | Status now | Task(s) that turn it green |
|---|---|---|
| **SC-2** OCR ≥5 scanned → **searchable** | 🟡 extraction-only, synthetic rasters | **Task 3** (OCR→index, end-to-end searchable) + **Task 4** (degraded scans + routing fixes) |
| **SC-1** 20–50 docs, PDF+DOCX+TXT+scanned, per-file pass/fail, idempotent | 🔴 open | **Task 1** (DOCX/TXT + report + idempotent) + **Task 2** (20–50 doc corpus) |
| **Failure quarantine + logs (§8)** | 🟡 flag only | **Task 1** (quarantine/`failed/` + `.error.txt` + JSONL report, consumes `ocr_failed`) |
| **M3 hybrid dense+BM25** | 🔴 open | **Task 5** |
| **M3 `<3s` first-token latency** | 🔴 open | **Task 6** (instrument + tune; honest number) |
| **SC-7 redeploy-from-scripts** | 🔴 open | **Task 7** |
| SC-3/4 cited+refusal+span-verify | ✅ | — (M2-8 stands) |
| SC-5 open original at cited page | ✅ | — (G-SC5/D-45) |
| SC-6 zero outbound | ✅ | re-proven in every task |

## Global Constraints

Every task implicitly includes these (verbatim from `CLAUDE.md` / `DECISIONS.md` / `RELAY.md`):

- **Synthetic / public / sanitized documents ONLY.** No real attorney/client data (real data is M6, onsite, written approval). Hard rules #1–#2.
- **Local-only, loopback-only.** Bind `127.0.0.1` only, **never `0.0.0.0`**. System Ollama at `127.0.0.1:11434` (not the bundled engine). No cloud, no API keys. Hard rule #4.
- **New installs/deps are owner-gated, one at a time** — state exactly what + why, install only as the approved step (each Task names its gate).
- **D-11 model pins are frozen:** `qwen3:14b=bdbd181c33f2`, `bge-m3=790764642607`, `RERANKER_REVISION` in `reranker.py`. Changing them forces re-index/re-eval — don't.
- **Document bodies + stores + results stay git-ignored (D-28):** `documents/`, `pipeline/.lancedb*/`, `eval/results/`. Never commit a body or a secret.
- **Do NOT touch the live `pipeline/.lancedb` store or the M2-8 artifacts** (`eval/results/run-2026-06-20-m2.jsonl`, `…-m2-rerun.jsonl`, `grades-2026-06-20-m2.md`) — they back M2-8 = FINAL PASS (D-40). All new indexing goes into a **separate** store, `pipeline/.lancedb_full`.
- **Manual eval scoring only** — an auto-scorer is approval-gated tooling; reading-aid scripts are fine (no pass/fail emitter).
- **The verifier fails conservatively** (D-38) — never weaken fabrication rejection to chase a metric.
- **Air-gap = egress-monitored (D-31):** every full run carries an `lsof`/`nettop` monitor proving zero non-loopback; append to git-ignored `eval/results/egress-*.log`.
- **Tests are `unittest`**, run as `.venv/bin/python -m unittest tests.test_X -v` from `pipeline/`.

---

## File Structure (created / modified across the plan)

- `pipeline/extractors.py` *(new, T1)* — per-type extraction: `pdf` (delegates to `ingestion`, OCR-aware), `docx` (python-docx), `txt`/`md` (read). One responsibility.
- `pipeline/ingest_pipeline.py` *(new, T1)* — the §8 orchestrator: scan → identify → route → checksum-dedup → per-file JSONL report → quarantine (consumes `ocr_failed`).
- `documents/synthetic_corpus/` *(extended, T2; git-ignored)* — 20–50 docs incl. DOCX/TXT/scanned.
- `pipeline/ingestion.py` *(modify, T4)* — routing fixes (sparse-digital page; mixed text+image page) + confidence threshold.
- `pipeline/make_scans.py` *(new, T4)* — synthesize **degraded** image-only PDFs (skew/noise/low-DPI/JPEG) from synthetic docs.
- `pipeline/build_full_store.py` *(new, T3)* — ingest+chunk+embed the corpus (OCR included) into `pipeline/.lancedb_full` (NOT `.lancedb`).
- `pipeline/retrieval.py` *(modify, T5)* — opt-in hybrid dense+BM25 behind the matter pre-filter.
- `pipeline/answering.py` *(modify, T6)* — side-channel first-token timing; `answer()` body unchanged (M2-7 parity).
- `pipeline/run_latency.py` *(new, T6)* — TTFT harness over the golden set.
- `deploy/` *(new, T7)* — `up.sh` / `down.sh` / `restore.sh` / `README.md`.
- `pipeline/tests/test_*.py` *(new per task)*.

## Sequencing & Dependencies

`T1 → T2 → T3 → T4` are ordered (orchestrator → corpus → OCR integration → OCR robustness). `T5`, `T6`, `T7` are independent of each other and follow T3 in priority order (retrieval quality → latency → deployment). Each Task is owner-gated where it installs.

---

### Task 1: Multi-format ingestion orchestrator (DOCX/TXT) + idempotent re-ingest + per-file report + quarantine

**Closes (chart):** SC-1 *mechanics* (per-file pass/fail, idempotent) + **Failure quarantine + logs (§8)**.

**Owner-gated install:** `python-docx` (pure-Python, no model/network). State + install as the approved step; pin the version.

**Files:** Create `pipeline/extractors.py`, `pipeline/ingest_pipeline.py`; Test `pipeline/tests/test_ingest_pipeline.py`.

**Interfaces:**
- Consumes: `ingestion.extract_pages(pdf_path)`, `ingestion.extract_pages_ocr(pdf_path, dpi, min_confidence)` (existing → page records `{source_filename, page_number, page_text, source, ocr_failed, confidence}`).
- Produces:
  - `extractors.extract(path) -> list[dict]` — normalized `{source_filename, page_number, page_text, source, ocr_failed}` for `.pdf/.docx/.txt/.md`. PDFs per-page route (text layer → `extract_pages`, image-only → `extract_pages_ocr`); DOCX/TXT/MD → single `page_number=1` record (no real pages, §8 step 5).
  - `ingest_pipeline.ingest_dir(src_dir, report_path, quarantine_dir, seen_checksums=None) -> dict` → `{"ingested":[...], "skipped_duplicate":[...], "quarantined":[{"file","reason"}], "needs_review":[...], "report_path"}`, writing a JSONL report (one record/file: filename, sha256, type, page_count, status ∈ {ingested,duplicate,quarantined,needs_review}, reason). **Idempotent** (checksum-seen → duplicate). **Fail-loud** (unreadable/corrupt/unsupported → `quarantine_dir` + `<name>.error.txt`). **Consumes `ocr_failed`:** any extracted page with `ocr_failed=True` → the doc is `needs_review` (low-OCR-confidence), **not indexed as authoritative** (§8 "below threshold → flag, don't index garbage").

- [ ] **Step 1: Write the failing test** — `pipeline/tests/test_ingest_pipeline.py`

```python
import sys, tempfile, unittest
from pathlib import Path
PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
from extractors import extract
from ingest_pipeline import ingest_dir

class TestExtractors(unittest.TestCase):
    def test_txt_extracts_single_page(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "memo.txt"
            p.write_text("SYNTHETIC — Retainer is $5,000.", encoding="utf-8")
            pages = extract(p)
            self.assertEqual(len(pages), 1)
            self.assertEqual(pages[0]["page_number"], 1)
            self.assertIn("$5,000", pages[0]["page_text"])

class TestIngestPipeline(unittest.TestCase):
    def test_report_idempotent_and_quarantine(self):
        with tempfile.TemporaryDirectory() as d:
            src, q = Path(d) / "in", Path(d) / "failed"
            src.mkdir(); q.mkdir()
            (src / "a.txt").write_text("SYNTHETIC alpha clause", encoding="utf-8")
            (src / "b.bin").write_bytes(b"\x00\x01not a document")
            report = Path(d) / "report.jsonl"
            r1 = ingest_dir(src, report, q)
            self.assertEqual(len(r1["ingested"]), 1)
            self.assertEqual(len(r1["quarantined"]), 1)
            self.assertTrue((q / "b.bin.error.txt").exists())
            r2 = ingest_dir(src, report, q, seen_checksums={x["checksum"] for x in r1["ingested"]})
            self.assertEqual(len(r2["ingested"]), 0)
            self.assertEqual(len(r2["skipped_duplicate"]), 1)
```

- [ ] **Step 2: Run, verify fail** — `cd pipeline && .venv/bin/python -m unittest tests.test_ingest_pipeline -v` → FAIL (`No module named 'extractors'`).
- [ ] **Step 3: Install gated dep** — state it, then `.venv/bin/pip install "python-docx==1.1.2"`; record exact version.
- [ ] **Step 4: Implement `extractors.py`** — dispatch on suffix; PDF via `ingestion` (per-page OCR routing), DOCX via `docx.Document(path).paragraphs`, TXT/MD via `read_text`; unsupported suffix → raise `ValueError` (orchestrator → quarantine).
- [ ] **Step 5: Implement `ingest_pipeline.py`** — SHA-256 checksum, duplicate-skip, `try extract` else quarantine + `.error.txt`, `ocr_failed`→`needs_review`, per-file JSONL report, summary dict.
- [ ] **Step 6: Run, verify pass.**
- [ ] **Step 7: Egress check** — socket-guard test (pattern: `tests/test_api.py::TestLoopbackOnlyEgress`) proving `ingest_dir` makes **zero** network connections; run, confirm.
- [ ] **Step 8: Commit** — `git add pipeline/extractors.py pipeline/ingest_pipeline.py pipeline/tests/test_ingest_pipeline.py pipeline/requirements.txt && git commit -m "feat(ingest): multi-format orchestrator — idempotent, per-file report, quarantine (SC-1 mechanics + §8)"`

**Scope guards:** no embedding/indexing here (T3); live store + eval untouched; DOCX/TXT page metadata best-effort `page_number=1` (note it, don't fake splits).

---

### Task 2: Broaden the synthetic corpus to 20–50 documents (multi-format)

**Closes (chart):** SC-1 corpus size + format coverage.

**Owner-gated install:** none.

**Files:** ~14–44 git-ignored synthetic docs under `documents/synthetic_corpus/` (all four `document_type`s; **≥3 DOCX**, **≥3 TXT/MD**, **≥5 scanned**); Test `pipeline/tests/test_corpus_breadth.py`.

**Interfaces:** Consumes `ingest_pipeline.ingest_dir` (T1). Produces a corpus that ingests to ≥20 docs across ≥4 types and ≥3 formats, all `ingested` (or intentionally `quarantined`/`needs_review` with a logged reason).

- [ ] **Step 1: Write the failing test** — `test_corpus_breadth.py`: ingest `documents/synthetic_corpus/`; assert `len(report.ingested) >= 20`, formats `>= {".pdf",".docx",".txt"}`, and all four `document_type`s present (derive type from a tracked per-file sidecar/manifest).
- [ ] **Step 2: Run, verify fail** (corpus too small).
- [ ] **Step 3: Author the docs** — fabricated, clearly `SYNTHETIC — NOT REAL`; varied matters/clients; small. Rasterize ≥5 to image-only PDFs (clean here; degraded variants are T4).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Egress check** — ingest of the full dir = zero non-loopback (monitor → `eval/results/egress-<date>-t2.log`).
- [ ] **Step 6: Commit** — bodies git-ignored; commit test + tracked type sidecar only: `git commit -m "test(corpus): 20–50 doc multi-format synthetic corpus ingests (SC-1)"`

**Scope guards:** synthetic only; no real names/templates; bodies under git-ignored `documents/` (D-28).

---

### Task 3: End-to-end OCR integration — OCR pages become retrievable (SC-2, fully searchable)

**Closes (chart):** SC-2 *end-to-end searchable* (G-SC2 proved extraction; this proves an OCR'd page is chunked, embedded, and returned by `answer()` with a verified citation). Into a **separate** store.

**Owner-gated install:** none.

**Files:** Modify `pipeline/chunking.py` (ensure OCR page records flow through, carrying `source="tesseract"` provenance into chunk metadata); Create `pipeline/build_full_store.py`; Test `pipeline/tests/test_ocr_retrieval_e2e.py`.

**Interfaces:** Consumes `extractors.extract` (T1), `chunking.chunk_corpus(pdf_dir, manifest_path, out_dir)`, `embed_store.build_store(chunks_path, db_path, table_name)`, `answering.answer(question, matter, top_k, db_path)`. Produces a populated `pipeline/.lancedb_full` whose chunks include OCR pages; `answer(q, matter, db_path=FULL_DB)` returns a grounded, span-verified citation to an OCR'd page.

- [ ] **Step 1: Write the failing test** — `test_ocr_retrieval_e2e.py`: build/reuse `.lancedb_full` from a scanned synthetic doc; `answer(<question answerable only from an OCR'd page>, matter=<that matter>, db_path=FULL_DB)`; assert a citation whose `filename` is the scanned doc, correct `page`, `rejected_claims == []`, and the span verifies (chunk-derived D-38/D-19).
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement `build_full_store.py`** — ingest T2 corpus → chunk (OCR pages included) → `build_store(chunks_path, db_path=".lancedb_full")`; embedding hits `bge-m3` on loopback Ollama only.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Egress + isolation** — (a) embedding egress-monitored, zero non-loopback (`eval/results/egress-<date>-t3.log`); (b) assert live `.lancedb` mtime/tree digest **unchanged**; (c) M2-8 result files' SHAs unchanged.
- [ ] **Step 6: Commit** — `git commit -m "feat(ocr): wire OCR pages into chunk→embed→index; scanned doc is end-to-end searchable (SC-2)"`

**Scope guards:** build ONLY into `.lancedb_full`; never re-embed `.lancedb`; no eval re-run; answering/verifier unchanged (only `db_path` differs).

---

### Task 4: OCR robustness — degraded scans + routing fixes (hardens SC-2 short of real data)

**Closes (chart):** the SC-2 yellow's remaining concern ("validated only on **clean 300-DPI synthetic rasters, not real scans**") as far as is possible without real data, **plus** the two Tester routing notes (`_MIN_TEXT_LAYER_CHARS` sparse-page misroute; mixed text+image page not OCR'd) and §8 "OCR gibberish → confidence threshold, flag, don't index."

**Owner-gated install:** `Pillow` **only if not already present** (likely already a Docling/torch dep — check `.venv/bin/python -c "import PIL"` first; install `Pillow` gated only if it errors). Tesseract is already installed (D-46).

**Files:** Modify `pipeline/ingestion.py` (routing + confidence); Create `pipeline/make_scans.py` (degraded-scan synthesis); Test `pipeline/tests/test_ocr_robustness.py`.

**Interfaces:**
- Produces: `make_scans.degrade_to_scanned_pdf(src_pdf, out_pdf, dpi=150, rotate_deg=1.2, noise=0.04, jpeg_quality=60)` — renders each page to an image, applies skew/Gaussian-noise/JPEG, writes an image-only PDF approximating a real scan.
- Modifies routing in `ingestion`: a page routes to OCR **iff** it has negligible extractable text **AND** substantial image coverage (use `page.get_text("dict")` char count + `page.get_images()`/image-area ratio) — so a **sparse-but-digital** page (logo + few words, real text layer, no full-page image) stays on the PyMuPDF path. A **mixed** page (real text layer **and** a large embedded image) is additionally OCR'd and the OCR text merged with the text-layer text (dedup), so embedded-image text isn't lost. Low-confidence OCR still sets `ocr_failed=True` (feeds T1 `needs_review`).

- [ ] **Step 1: Write the failing tests** — `test_ocr_robustness.py`:
  - **degraded scan recovers:** `degrade_to_scanned_pdf` a known synthetic doc at 150 DPI + skew + noise; `extract_pages_ocr` recovers ≥3 known spans on their correct pages at confidence ≥ the floor; a heavily-degraded page below the floor sets `ocr_failed=True` (flagged, not silently trusted).
  - **sparse-digital not misrouted:** a born-digital page with a real but <20-char text layer and no full-page image → `extract_pages` path, `source=="pymupdf"`, `ocr_failed=False` (NOT routed to OCR).
  - **mixed page:** a page with a text layer + a large embedded scanned image of known text → the embedded text is recovered (OCR merged), not dropped.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `make_scans.py` (Pillow degradations) + the `ingestion` routing/merge/confidence changes.
- [ ] **Step 4: Run, verify pass** (+ run `tests` for `ingestion`/G-SC2 + the born-digital byte-identical check to confirm no regression on clean docs).
- [ ] **Step 5: Egress check** — OCR over degraded scans = zero network (socket-guard); append `eval/results/egress-<date>-t4.log`.
- [ ] **Step 6: Commit** — `git commit -m "feat(ocr): degraded-scan robustness + sparse/mixed-page routing fixes + confidence floor (SC-2 hardening, §8)"`

**Scope guards:** synthetic degradations only (real-scan validation remains **M6**, owner-gated — state this honestly in the report); don't weaken the clean-doc fast path; don't change model pins.

---

### Task 5: Hybrid dense + BM25 retrieval (G-HYB)

**Closes (chart):** M3 hybrid dense+BM25 (currently dense-only, `retrieval.py:43 table.search(query_vec)`).

**Owner-gated install:** `tantivy` (LanceDB full-text-search backend) — one-time, local index, no model/network fetch.

**Files:** Modify `pipeline/retrieval.py`; Test `pipeline/tests/test_hybrid_retrieval.py`.

**Interfaces:** Consumes `embed_store.open_table(db_path, table_name)` + the existing matter pre-filter. Produces `retrieve(question, matter=None, top_k=5, db_path=None, rerank=False, candidate_k=20, hybrid=False)` — `hybrid=True` returns RRF-fused dense+BM25 (matter pre-filter still applied first); `hybrid=False` is unchanged.

- [ ] **Step 1: Write the failing test** — against `.lancedb_full` (or a fixture): a keyword-exact query (rare clause term/number) returns the correct chunk at rank 0 under `hybrid=True`; matter pre-filter still kills cross-matter; `hybrid=False` output unchanged.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Install `tantivy`** (gated) + implement the hybrid path (FTS index on `text`, dense search, RRF fuse, pre-filter intact).
- [ ] **Step 4: Run, verify pass** (+ `tests.test_retrieval` for no dense regression).
- [ ] **Step 5: Measure lift (reading-aid, manual)** — 63 present-fact questions, `hybrid=True` vs `False`; record rank@1/MRR delta in a tracked note (no auto-scorer). State honestly whether it helps at this scale (mirror D-36 reranker honesty).
- [ ] **Step 6: Commit** — `git commit -m "feat(retrieval): opt-in hybrid dense+BM25 (RRF) behind matter pre-filter (M3)"`

**Scope guards:** matter pre-filter (D-18) upstream of fusion; `hybrid` defaults off; reranker default unchanged (D-36); pins unchanged.

---

### Task 6: First-token latency instrumentation + tuning (G-LAT)

**Closes (chart):** M3 `<3s` first-token (uninstrumented, ~7s/Q, qwen3 "thinking").

**Owner-gated install:** none.

**Files:** Modify `pipeline/answering.py` (side-channel TTFT; **`answer()` body unchanged** — M2-7 parity); Create `pipeline/run_latency.py`; Test `pipeline/tests/test_latency_harness.py`.

**Interfaces:** Consumes `answering._chat`, `embed_store.ollama_url()`. Produces `run_latency.measure(question, matter, db_path) -> {"ttft_s": float, "total_s": float}` (TTFT = request-send → first non-empty content token from the Ollama stream) + a summary writer to git-ignored `eval/results/latency-<date>.jsonl`.

- [ ] **Step 1: Write the failing test** — `measure(...)` returns positive floats `ttft_s <= total_s`; assert it does NOT alter `answer()`'s output (call `answer()` for the same input; response body unchanged — parity guard).
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** streaming TTFT (`stream=True` to Ollama; stamp first token) + `run_latency.py`. Try documented knobs toward <3s: qwen3 **no-think** for first token, `keep_alive` warm, bounded `num_predict`. Record the knob + honest TTFT.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Harness + egress** — 63 questions, zero non-loopback (`eval/results/egress-<date>-t6.log`); record TTFT mean/median/p95. If <3s isn't reached, record the honest number + that thinking-mode dominates (a legitimate pre-M4 datapoint, not a silent miss).
- [ ] **Step 6: Commit** — `git commit -m "feat(latency): first-token instrumentation + tuning knobs; answer() parity preserved (G-LAT)"`

**Scope guards:** `/answer` response body unchanged (M2-7 parity, D-41); pins unchanged; streaming loopback-only.

---

### Task 7: Scripted redeploy + restore drill (SC-7)

**Closes (chart):** SC-7 redeploy-from-scripts. Builds on the M2-9 Compose stack (D-43) — **compose-only** loopback boundary (D-43a).

**Owner-gated install:** none new (Docker/Compose already approved, D-41/D-43).

**Files:** Create `deploy/up.sh`, `deploy/down.sh`, `deploy/restore.sh`, `deploy/README.md`; Test `pipeline/tests/test_deploy_scripts.py`.

**Interfaces:** Consumes `docker-compose.yml` (D-43) + the git-ignored `.lancedb` volume. Produces `up.sh` (build + `docker compose up -d` + health-check `127.0.0.1:8000/health`), `down.sh` (`docker compose down` + verify port released), `restore.sh` (restore the LanceDB store from a local tarball into the mounted volume), `README.md` (documented clean-machine steps).

- [ ] **Step 1: Write the failing test** — `test_deploy_scripts.py`: scripts exist + executable; **no script publishes `0.0.0.0`** and none uses a bare `docker run -p` (grep guard — D-43a, compose-only); `docker-compose.yml` still binds `127.0.0.1:8000:8000`.
- [ ] **Step 2: Run, verify fail** (scripts absent).
- [ ] **Step 3: Write scripts + README** — compose-only; loopback health check; restore drill from a local tarball of `.lancedb`.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Live drill (egress-monitored)** — `down.sh` → `up.sh` from clean, confirm `/health` + one `/answer` over loopback, then a `restore.sh` round-trip; monitor proves zero non-loopback (`eval/results/egress-<date>-t7.log`); host Ollama bind unchanged; `down.sh` leaves no bound port. **Stop condition:** if any step would require binding `0.0.0.0` / setting `OLLAMA_HOST`, STOP and surface it.
- [ ] **Step 6: Commit** — `git commit -m "feat(deploy): scripted redeploy + restore drill, compose-only loopback (SC-7)"`

**Scope guards:** compose-only (never `docker run -p`); never `0.0.0.0`; never `OLLAMA_HOST`; restore drill uses a synthetic store only.

---

## After all seven tasks — the SC scorecard

| SC / item | Before | After |
|---|---|---|
| SC-1 (20–50 docs, multi-format, per-file report, idempotent) | 🔴 | ✅ T1–T2 |
| SC-2 (OCR scanned → searchable end-to-end + robust) | 🟡 | ✅ T3 + T4 (real-scan final validation = M6) |
| §8 quarantine + logs | 🟡 | ✅ T1 |
| M3 hybrid dense+BM25 | 🔴 | ✅ T5 |
| M3 `<3s` first-token | 🔴 | ✅ instrumented T6 (honest number) |
| SC-3/4 cited+refusal+span-verify | ✅ | ✅ (M2-8 stands) |
| SC-5 open original at cited page | ✅ | ✅ (G-SC5) |
| SC-6 zero outbound | ✅ | ✅ (re-proven each task) |
| SC-7 redeploy-from-scripts | 🔴 | ✅ T7 |

All green → the CE_PLAN §2 gate ("GO for attorney demo") is met → unlocks the **owner** decision on CE_PLAN Milestone 4 (attorney UAT), then M4-5 hardware (no purchase on spec, D-21/D-22). Real data stays M6 (onsite, written approval).

**The one honest residual:** SC-2's "real scans" can only be *finally* validated on real documents (M6, gated). T4 closes the gap as far as synthetic data allows (degraded scans + routing fixes); the plan does not pretend synthetic rasters equal real scans.

## Carry-forward (tracked, outside this plan)

- F-026 recall gap (top_k/reranker/chunking); `answering._norm` escape-alignment (fails safe); native-Linux `host.docker.internal` portability (D-43b). All in `TASKS_M2.md` Risks.
