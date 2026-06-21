# SAM-style Local Document-Intelligence UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. **Executed through the Planner→Builder→Reviewer→Tester relay** — but per the owner's direction this round, the Builder implements **all seven tasks** in one batch (each still TDD + its own commit + its own acceptance gate), then the Reviewer audits every task and the Tester independently verifies every task.

**Goal:** Give the attorney the experience they love from "SAM" — a left-nav app shell with a Document Hub (upload + manage), matter-scoped chat with cited answers, visual retrieval evidence with the cited span highlighted, and a privacy/settings view — but **100% local, loopback-only, air-gapped**, over the existing citation-grade pipeline.

**Architecture:** Extends the existing loopback FastAPI app (`pipeline/api.py`). Adds a SQLite catalog (`catalog.py`: matters, documents, threads), an async ingest worker (`kb_ingest.py`), and FastAPI routers for `/matters`, `/kb`, `/chat`, `/settings`. The front end is a **single static app** (`static/app.html` + `static/app.js` + `static/app.css`) with client-side view switching — **vanilla JS, no build step, no framework toolchain, and NO CDN (all assets local — a CDN fetch would be egress)**. A **dedicated live store `.lancedb_kb`** holds the attorney's uploaded knowledge base; every eval store is untouched.

**Tech Stack:** Python 3.12 (`pipeline/.venv`), FastAPI/uvicorn (loopback), SQLite (stdlib `sqlite3`), PyMuPDF (`fitz` — page thumbnails + span-highlight), Tesseract/`pytesseract` (OCR, already installed), `bge-m3`+`qwen3:14b` on loopback Ollama, LanceDB. Front end: vanilla HTML/CSS/JS, no build, no CDN. Tests: `unittest` (NOT pytest).

## Product-boundary guardrails (the nav is curated ON PURPOSE)

This is a **cited-retrieval tool**, NOT an AI lawyer and NOT an autonomous agent (CLAUDE.md hard rules #1–#6). The left nav is deliberately limited to **New Chat · Matters · Document Hub · Chat History · Settings**. Do **NOT** add drafting/templates, advice/outcome features, deadlines/calendar/to-do, billing/finance, or anything that *acts* (sends/files/notifies). Those are out of scope by the project's own rules (future capabilities = a separate scope+safety review, CE_PLAN M8). Building any of them is a plan violation.

## Global Constraints

Every task implicitly includes these (verbatim from `CLAUDE.md` / `DECISIONS.md`):

- **Cited retrieval only; no advice, no drafting, no actions** (hard rules #1–#6). No SMTP/network actions; the answering path has no action tools and no egress (D-2).
- **Synthetic / public / sanitized documents ONLY** — no real attorney/client data (real data is M6, onsite, written approval).
- **Local-only, loopback-only.** Bind `127.0.0.1`, **never `0.0.0.0`**. System Ollama `127.0.0.1:11434`. **NO CDN / no remote assets at runtime** — all JS/CSS/fonts are local files (a CDN load is non-loopback egress and breaks the air-gap).
- **D-11 model pins frozen:** `qwen3:14b=bdbd181c33f2`, `bge-m3=790764642607`. Don't change them.
- **Dedicated live store `pipeline/.lancedb_kb` (git-ignored).** Do **NOT** touch `pipeline/.lancedb` (M2-8 baseline), `.lancedb_full`, `.lancedb_hyb`, or any `eval/results/` artifact. Verify (mtime/SHA) they're unchanged.
- **Managed docs live under git-ignored `documents/kb/<matter>/`** (D-28). The catalog DB `pipeline/.kb_catalog.db` and `.lancedb_kb` are git-ignored. Never commit a document body or DB.
- **Matter-scoped throughout (D-18):** retrieval hard-pre-filters by `matter` before similarity. Matter values are slugged/validated (no path injection).
- **Delete = remove-from-KB only (hard rule #5).** It removes the managed copy under `documents/kb/` + that doc's chunks from `.lancedb_kb` + the catalog row. It must be structurally incapable of touching any path outside `documents/kb/`. The attorney's originals are never read or deleted.
- **Citations stay chunk-derived (D-38) + span-verified (D-19).** The UI never invents or displays a model-asserted page.
- **Air-gap = egress-monitored (D-31):** network-bearing runs (embedding, answering) carry an `lsof`/`nettop` monitor proving zero non-loopback; append **real samples** (not an empty header) to git-ignored `eval/results/egress-<date>-uiN.log`.
- **Tests are `unittest`**, run `.venv/bin/python -m unittest tests.test_X -v` from `pipeline/`.

---

## File Structure

- `pipeline/catalog.py` *(new, T2)* — SQLite persistence: `matters`, `documents`, `threads`/`messages` tables + typed accessors. One responsibility: durable app state.
- `pipeline/kb_ingest.py` *(new, T3)* — async ingest worker: save → `extractors.extract` → `chunking` → embed → upsert into `.lancedb_kb` → status transitions. One responsibility: turn an upload into indexed, matter-scoped chunks.
- `pipeline/pdf_view.py` *(new, T5)* — PyMuPDF helpers: render a page to a PNG thumbnail; locate a verbatim span on a page (`page.search_for`) and produce a highlighted page image / annotated PDF. One responsibility: visual evidence.
- `pipeline/api.py` *(modify, all tasks)* — mount the routers + serve the static app; keep existing `/health`, `/answer`, `/source`.
- `pipeline/routes_matters.py`, `routes_kb.py`, `routes_chat.py`, `routes_settings.py` *(new)* — the four nav surfaces' endpoints.
- `pipeline/static/app.html`, `app.css`, `app.js` *(new, T1; extended per task)* — the single-page shell + views. Local assets only.
- `pipeline/tests/test_*.py` *(new per task)*.

## Sequencing

`T1 (shell) → T2 (matters) → T3 (Document Hub) → T4 (chat + history) → T5 (visual evidence + highlight) → T6 (rich answer) → T7 (settings)`. T2 underpins T3/T4; T5/T6 enrich T4's rendering; T7 is independent (last). Each task is owner-gated where it installs (only T6 may need one).

---

### Task 1: App shell + left nav + local static-asset serving

**Closes:** the persistent SAM-like layout — a left sidebar (**New Chat · Matters · Document Hub · Chat History · Settings**) + a main content pane with client-side view switching; all assets served **locally** (no CDN).

**Owner-gated install:** none.

**Files:** Create `pipeline/static/app.html`, `pipeline/static/app.css`, `pipeline/static/app.js`; Modify `pipeline/api.py` (serve `GET /app` → `app.html`; mount `static/` for local assets via `FileResponse`/a small static route, **not** a CDN); Test `pipeline/tests/test_app_shell.py`.

**Interfaces:**
- Produces: `GET /app` → the shell HTML; `GET /static/{asset}` → local CSS/JS (path-locked to `pipeline/static/`, like the existing `/source` lock). `app.js` exposes a `showView(name)` router over views `chat|matters|hub|history|settings`.

- [ ] **Step 1: Write the failing test** — `test_app_shell.py` (FastAPI `TestClient`): `GET /app` → 200, `text/html`, body contains the five nav labels (`New Chat`, `Matters`, `Document Hub`, `Chat History`, `Settings`); `GET /static/app.js` → 200 `application/javascript`; a path-traversal `GET /static/../api.py` → 404; **assert the HTML/JS/CSS contain no `http://`/`https://` external asset URL** (air-gap: no CDN) — grep the served bodies for `src="http` / `href="http` / `@import url(http` and assert none.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** the shell (`app.html` sidebar + content pane; `app.css` SAM-like dark sidebar; `app.js` `showView`), the `/app` + path-locked `/static` routes, and the no-external-asset rule (system fonts only).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git add pipeline/static/app.* pipeline/api.py pipeline/tests/test_app_shell.py && git commit -m "feat(ui): app shell + left nav + local-only static assets (no CDN)"`

**Scope guards:** no nav items beyond the five (product-boundary guardrail); no CDN/remote assets; don't break the existing `/`, `/answer`, `/source`.

---

### Task 2: Matters (backend catalog + UI)

**Closes:** matter as a first-class concept — the spine of matter-scoped retrieval (D-18): list matters, create a matter, see each matter's doc count; a matter switcher used by Chat + Document Hub.

**Owner-gated install:** none (`sqlite3` is stdlib).

**Files:** Create `pipeline/catalog.py`, `pipeline/routes_matters.py`; Modify `pipeline/api.py` (include the router); Test `pipeline/tests/test_matters.py`.

**Interfaces:**
- Produces: `catalog.create_matter(display_name) -> {"id","slug","display_name","created"}` (slug is a path-safe lowercase-hyphen form; rejects empty/duplicate); `catalog.list_matters() -> list[dict]` (with `doc_count`); `catalog.get_matter(slug)`. Routes: `GET /matters` → `{"matters":[...]}`; `POST /matters` `{display_name}` → the created matter (400 on empty/dupe). The catalog DB path is `pipeline/.kb_catalog.db` (git-ignored), overridable via arg for tests (temp DB).

- [ ] **Step 1: Write the failing test** — `test_matters.py`: `create_matter("Pemberton Logistics")` → slug `pemberton-logistics`; duplicate display name → `ValueError`/400; `list_matters()` includes it with `doc_count==0`; the slug has no `/`/`..` (path-safe). Route tests via `TestClient`: `POST /matters` then `GET /matters` reflects it; empty name → 400.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `catalog.py` (SQLite schema + matter accessors, parameterized queries — no string interpolation) + `routes_matters.py` + include in `api.py`. UI: a Matters view in `app.js` listing matters with doc counts + a "New matter" form; a shared matter-picker component reused by Chat/Hub.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(matters): SQLite catalog + matters list/create + matter switcher (D-18 spine)"`

**Scope guards:** slugs path-safe + validated (injection guard); catalog DB git-ignored; no matter inference from text (explicit selection only, D-35).

---

### Task 3: Document Hub — upload + async ingest + status table + safe delete

**Closes:** the screen you led with — drag/drop upload → async ingest into `.lancedb_kb` (matter-scoped) → a table (Name · Matter · Size · Status · Updated · view · delete) with the `Parsing → Ready` lifecycle. **End-to-end proof:** an uploaded synthetic doc becomes answerable.

**Owner-gated install:** none (reuses `python-docx`/Tesseract from prior tasks).

**Files:** Create `pipeline/kb_ingest.py`, `pipeline/routes_kb.py`; Modify `pipeline/catalog.py` (documents table), `pipeline/api.py`; Test `pipeline/tests/test_kb_ingest.py`, `pipeline/tests/test_kb_routes.py`.

**Interfaces:**
- Consumes: `extractors.extract` (OCR-aware), `chunking` (chunk a doc's pages), `embed_store.build_store`/an upsert into `.lancedb_kb`, `catalog`.
- Produces: `kb_ingest.ingest_document(doc_id, file_path, matter_slug, db_path) -> status` (extract→chunk→embed→upsert into `.lancedb_kb` table `chunks` with the matter payload; sets `ready`/`needs_review`(if any `ocr_failed`)/`failed`(reason); idempotent on checksum). Routes: `POST /kb/upload` (multipart `file` + `matter`) → save under `documents/kb/<slug>/`, catalog row `parsing`, schedule `ingest_document` as a FastAPI `BackgroundTask`, return the row; `GET /kb/documents?matter=` → catalog rows; `GET /kb/source/{doc_id}` → the managed PDF (path-locked to `documents/kb/`); `DELETE /kb/documents/{doc_id}` → remove chunks from `.lancedb_kb` + the managed copy + the row.

- [ ] **Step 1: Write the failing tests** — `test_kb_ingest.py`: `ingest_document` on a synthetic TXT/PDF into a temp `.lancedb_kb` → status `ready`, chunks present under the right `matter`; an OCR-failed page → `needs_review`; an uploaded doc is **answerable**: `answer(<q>, matter=<slug>, db_path=temp_kb)` returns a span-verified citation to it. `test_kb_routes.py` (`TestClient`): `POST /kb/upload` → row `parsing`; after the background task runs → `GET /kb/documents` shows `ready`; **DELETE removes the chunks + the managed copy + the row, and a crafted `doc_id`/path cannot escape `documents/kb/`** (security test — assert no file outside that dir is touched); `/kb/source` path-locked; oversized/unsupported upload → 400/`failed`.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** the documents catalog table, `kb_ingest.py`, `routes_kb.py`, and the Document Hub UI (drag/drop zone + matter picker + the status table with view/delete + polling `GET /kb/documents`).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Egress + isolation** — embedding run egress-monitored, zero non-loopback (`eval/results/egress-<date>-ui3.log`); assert `.lancedb`/`.lancedb_full`/`.lancedb_hyb` + M2-8 artifacts unchanged (mtime/SHA).
- [ ] **Step 6: Commit** — `git commit -m "feat(kb): Document Hub — drag/drop upload, async ingest into .lancedb_kb, status table, safe delete (matter-scoped)"`

**Scope guards:** writes ONLY to `.lancedb_kb` + `documents/kb/`; delete structurally cannot touch anything outside `documents/kb/`; never touch eval stores; synthetic uploads only.

---

### Task 4: Chat shell + Chat History (matter-scoped, cited answers)

**Closes:** the conversational surface — New Chat → ask within the active matter → cited answer from `.lancedb_kb`; threads persist and list under Chat History.

**Owner-gated install:** none.

**Files:** Create `pipeline/routes_chat.py`; Modify `pipeline/catalog.py` (threads/messages), `pipeline/api.py`, `pipeline/static/app.js`; Test `pipeline/tests/test_chat_routes.py`.

**Interfaces:**
- Consumes: `answering.answer(question, matter, top_k, db_path=KB_DB)`, `catalog`.
- Produces: `POST /chat` `{question, matter, thread_id?}` → runs `answer(...)` scoped to `matter` against `.lancedb_kb`, persists the user+assistant turn under a thread, returns `{thread_id, answer_text, citations, rejected_claims, grounding_chunks}`; `GET /chat/threads` → thread list (title, updated); `GET /chat/threads/{id}` → messages. Citations stay chunk-derived (D-38). Refusal path (empty KB / no match) returns the exact D-30 sentence.
- [ ] **Step 1: Write the failing test** — `test_chat_routes.py`: with a seeded `.lancedb_kb` (a synthetic doc under matter X), `POST /chat {question, matter:X}` → an answer with a chunk-derived, span-verified citation, `rejected_claims==[]`, and a persisted `thread_id`; `GET /chat/threads` lists it; a question under an **empty** matter → the D-30 refusal, no citation; the `/chat` result for matter X never returns a chunk from matter Y (matter-scoping).
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** threads/messages in `catalog.py`, `routes_chat.py`, and the Chat + Chat History views (message thread, input, active-matter picker, thread list).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Egress** — a live `/chat` call egress-monitored, zero non-loopback (`eval/results/egress-<date>-ui4.log`).
- [ ] **Step 6: Commit** — `git commit -m "feat(chat): matter-scoped cited chat over .lancedb_kb + persisted threads/history"`

**Scope guards:** answers ONLY from `.lancedb_kb` scoped to the chosen matter; no web/tool calls (D-2); refusal stays the D-30 substance gate; no model-asserted pages.

---

### Task 5: Visual retrieval evidence + cited-span highlight

**Closes:** SAM's "Knowledge Retrieval" card — show the actual retrieved **page thumbnails**, and **highlight the exact cited span** on the page (your last request). Strongest trust signal (verify-the-citation, D-5).

**Owner-gated install:** none (PyMuPDF already present).

**Files:** Create `pipeline/pdf_view.py`; Modify `pipeline/routes_kb.py` (thumbnail + highlight routes), `pipeline/static/app.js`; Test `pipeline/tests/test_pdf_view.py`.

**Interfaces:**
- Produces: `pdf_view.render_page_png(pdf_path, page_number, dpi=110) -> bytes` (a page thumbnail); `pdf_view.highlight_span_png(pdf_path, page_number, span_text, dpi=150) -> bytes` (locate `span_text` via `page.search_for`, draw a highlight rect, render PNG). Routes: `GET /kb/thumb/{doc_id}?page=N` → PNG; `GET /kb/highlight/{doc_id}?page=N&span=...` → PNG with the cited span highlighted (path-locked; span passed safely, not interpolated into a path). The Chat view renders, per citation, a thumbnail card that opens the highlighted page.
- [ ] **Step 1: Write the failing test** — `test_pdf_view.py`: `render_page_png(<synthetic pdf>, 1)` returns PNG bytes (`\x89PNG` header); `highlight_span_png(pdf, page, <a verbatim span from that page>)` returns PNG **and** the highlight rect is non-empty (the span was located via `search_for`); a span absent from the page → no crash, returns the plain page (graceful). Route tests: `/kb/thumb` + `/kb/highlight` path-locked to `documents/kb/` (traversal → 404).
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `pdf_view.py` + the routes + the Chat thumbnail/highlight card UI.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(ui): retrieved-page thumbnails + cited-span highlight (PyMuPDF, SC-5++)"`

**Scope guards:** thumbnails/highlights only from `documents/kb/` (path-locked); span located from the **verified** citation (never a model-asserted page); no new deps.

---

### Task 6: Rich answer formatting (markdown + inline citations + Sources)

**Closes:** SAM's polished answer — headings/bold/bullets, inline clickable source references, a Sources section — over the data `answer()` already returns.

**Owner-gated install:** **avoid** — render markdown with a **small local formatter in `app.js`** (headings, bold, lists) rather than a CDN library. If a server-side markdown lib is strongly preferred, that is an owner-gated `pip install markdown` — default to the local JS formatter (no dep, no CDN).

**Files:** Modify `pipeline/static/app.js`, `pipeline/static/app.css`; Test `pipeline/tests/test_answer_format.py` (a tiny JS-logic mirror in Python is not possible — instead test the **prompt/structure** server-side: that `answer_text` + `citations` carry what the formatter needs) + a documented manual visual check.

**Interfaces:**
- Produces (client-side): a formatter that turns `answer_text` into safe HTML (escape first, then apply minimal markdown), replaces the inline citation markers with **clickable source chips** wired to the Task-5 highlight, and renders a **Sources** list from the structured `citations`. No `innerHTML` of raw model text without escaping (XSS guard even locally).
- [ ] **Step 1: Write the failing test** — `test_answer_format.py` (`TestClient`): assert `/chat` returns the fields the formatter needs (`answer_text`, `citations[*].{filename,page,span,char_start,char_end}`) so the chips/Sources can render and link to `/kb/highlight`. (UI rendering itself is verified by the manual visual check in Step 4.)
- [ ] **Step 2: Run, verify fail** (if fields missing) / confirm contract.
- [ ] **Step 3: Implement** the local markdown formatter + inline source chips + Sources section + CSS; escape-before-format (XSS guard).
- [ ] **Step 4: Manual visual check** — documented: ask a question, confirm the answer renders with headings/bullets, each inline source chip opens the highlighted page, and the Sources list matches `citations`. Record the steps in the commit body.
- [ ] **Step 5: Commit** — `git commit -m "feat(ui): rich answer rendering — markdown + inline source chips + Sources (local formatter, no CDN)"`

**Scope guards:** local formatter only (no CDN lib); escape model text before rendering; chips link to the **verified** citation/highlight; no model-asserted pages.

---

### Task 7: Settings / System + privacy (air-gap) badge

**Closes:** a Settings view showing model + storage status, backup/restore hooks (reuse the SC-7 `deploy/restore.sh` story), and the headline **"100% local · 0 outbound"** privacy badge — your moat made visible.

**Owner-gated install:** none.

**Files:** Create `pipeline/routes_settings.py`; Modify `pipeline/api.py`, `pipeline/static/app.js`; Test `pipeline/tests/test_settings.py`.

**Interfaces:**
- Produces: `GET /settings/status` → `{"models":{"chat":"qwen3:14b","embed":"bge-m3"}, "ollama":"127.0.0.1:11434", "stores":{"kb_docs":N,"kb_chunks":M}, "egress":"loopback-only", "bind":"127.0.0.1"}` (read-only system facts — model names from the pins, store counts from `.lancedb_kb`/catalog, the loopback posture). The Settings view renders these + a green **"100% local · 0 outbound"** badge.
- [ ] **Step 1: Write the failing test** — `test_settings.py` (`TestClient`): `GET /settings/status` → 200 with `bind=="127.0.0.1"`, `egress=="loopback-only"`, the pinned model names, and integer store counts; assert it exposes **no secret/path** (just status).
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `routes_settings.py` + the Settings view + the privacy badge.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(settings): system/status view + 100%-local privacy badge"`

**Scope guards:** status is read-only (no mutating settings that could relax loopback/egress); the badge reflects real posture, not a hardcoded claim.

---

## After all seven tasks — run it locally

- [ ] Start the app on loopback: `cd pipeline && .venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000`; open **http://127.0.0.1:8000/app**.
- [ ] Smoke the full flow under an `lsof` monitor (zero non-loopback): create a matter → upload a synthetic doc (watch `Parsing → Ready`) → open Chat in that matter → ask a question → see the cited answer with a highlighted-span thumbnail → check Settings shows "100% local · 0 outbound". Append the monitor log to `eval/results/egress-<date>-ui-smoke.log`.
- [ ] Confirm the eval stores (`.lancedb`/`.lancedb_full`/`.lancedb_hyb`) + M2-8 artifacts are unchanged.

## Out of scope (do NOT build — product-boundary guardrail)

Drafting/templates, advice/outcome features, deadlines/calendar/to-do, billing/finance, any action-taking (send/file/notify), any CDN/remote asset, any cloud model. These are excluded by the project's hard rules; adding them is a plan violation. Real-data use stays M6 (owner-gated, written approval).
