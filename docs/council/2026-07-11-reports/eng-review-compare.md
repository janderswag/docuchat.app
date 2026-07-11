# Engineering + Product Audit — Review & Compare tab

> Council seat: adversarial engineering/product auditor. 2026-07-11.
> Everything below was verified by reading code; each claim carries file:line.
> Verdict tags: CONFIRMED = provable from code; PLAUSIBLE = strongly indicated, needs a live run.

## 0. Scope check: is the clause path inside the frozen answer engine?

**No — verified.** `clauses.py` and `grid.py` are pure *consumers* of the frozen path:
`clauses.py:28` imports `answer` from `answering.py` and loops over it; `grid.py:19-20`
does the same and reuses `clauses._classify`. Neither module is imported by
`answering.py` / `retrieval.py` / `verifier.py`. So **orchestration changes (streaming,
concurrency, caching, persistence, export, UI) require no golden gate.** The gate bites
only if we change `answer()`'s behavior (per-doc retrieval filters, second-pass flags,
model swaps) — flagged per-option below.

---

## (a) Latency anatomy of one review

`POST /clauses/review` is one synchronous request (`routes_clauses.py:34-54`). Inside it,
`extract_clauses` (`clauses.py:112-121`) runs a **sequential** for-loop over the taxonomy —
**20 clauses** (`data/clause_taxonomy.json`) — each iteration a full `answer()` call
(`answering.py:423`):

| Stage per clause | Code | Cost (measured, speed doc 2026-07-10) |
|---|---|---|
| Question embed (bge-m3) | `retrieval.py:135` | 30-80 ms warm, 1-3 s after 5-min idle (embedder has no keep_alive) |
| LanceDB matter-prefiltered top-5 | `retrieval.py:97-140` | 10-50 ms |
| **Non-streaming qwen3:14b call** | `answering.py:440` (`_chat`) | **~6-12 s warm** (prefill 1.8-3.5 s + decode 4-8 s) |
| Mechanical span verify | `answering.py:447` | ~1-10 ms |
| **Refusal second pass** (Move 1b) | `answering.py:454-464` | **+5-15 s** — wide hybrid retrieval + a SECOND full LLM call |

The killer interaction: for a checklist, "clause absent" is an *expected, common* outcome —
and every absent clause fires the refusal second pass, i.e. **the clauses that aren't there
cost twice as much as the ones that are.** A typical contract with ~half the checklist
missing: 20 × 6-12 s + ~10 × 5-15 s ≈ **3-6 minutes**, all inside one blocking HTTP
request, using the non-streaming `answer()` (not `answer_stream`), so not a single byte
returns until every clause is done.

Two aggravators:

1. **No interactive priority.** `routes_chat` marks chat activity to pause background
   ingest/digest LLM work; `routes_clauses.py` never touches `activity` (whole file,
   13-54), so a running digest extraction competes with the review for the one Ollama.
2. **What the user sees:** a single static line — `"Running the clause checklist over X …
   this can take a moment."` (`app.js:2417-2418`). No progress, no per-clause updates, no
   cancel, no cost estimate. "A moment" at minute four is the opposite of the product's
   honesty bar.

Compare cost is worse: docs × 20 cells, each cell a full `answer()` (+ second pass on
misses). 5 documents = 100-200 LLM calls. The UI never warns the user what they are about
to spend (`app.js:2557-2568`).

## (b) Timeout / tab-switch / app-close mid-review

- **PLAUSIBLE, high priority to verify: the packaged app times the review out at ~60 s.**
  The app is a pywebview/WKWebView shell (`desktop/launcher.py:11`). WKWebView `fetch`
  rides NSURLSession's default `timeoutIntervalForRequest` (60 s of *no bytes received*).
  `/clauses/review` sends zero bytes until fully done (routes_clauses.py:34 returns a
  plain JSON body), so any matter whose review exceeds ~60 s — i.e. essentially all of
  them — likely dies client-side with "Failed to fetch" while **the server keeps burning
  Ollama for minutes to compute a response nobody will receive** (sync route; uvicorn
  can't detect the disconnect). The grid is immune: its SSE stream (`routes_grid.py:43-58`)
  delivers bytes continuously, resetting the idle timer. This asymmetry alone argues for
  converting the review to the grid's streaming shape. *Verify in the packaged app before
  the council treats it as fact — browser QA misses WKWebView-only behavior (known class).*
- **Tab-switch inside the app: genuinely good.** UX-3 build-once (`app.js:9-12, 52-58`)
  hides views instead of rebuilding; the in-flight `await api(...)` keeps running and the
  result renders into the still-existing `#clause-results`. A finished review and a
  streaming grid both survive navigation. This is real, deliberate engineering.
- **App close / quit: total loss.** Nothing is persisted anywhere — no table, no file
  (catalog.py has `fact_review` for the digest only; grep shows zero clause/review
  storage). Re-running costs the full 3-6 minutes again.

## (c) Persistence

**None for the clause review.** The grid's only artifact is a client-side CSV built from
the in-memory `gridData` (`app.js:2489-2512`), and its Export button is enabled only by
the SSE `done` event (`app.js:2566, 2586`) — if the stream errors at cell 95/100, the
filled cells are on screen but **export stays disabled**. No history, no "last run"
timestamp, no doc-hash cache. Note the substrate is cache-friendly: `answer()` runs at
temperature 0 (`answering.py:159`), so the same doc set + taxonomy yields stable output —
a persisted review keyed on (matter, doc content hashes, taxonomy version) is sound.

## (d) Speed-to-insight options, ranked (effort/risk; gate exposure marked)

1. **Stream the review like the grid already streams (S, no risk, no gate).** The full
   pattern exists end-to-end in this codebase: SSE route (`routes_grid.py:35-58`),
   skeleton-then-fill client (`app.js:2570-2588`). Convert `/clauses/review` to SSE
   emitting `meta` (the 20 clauses as skeleton rows) then one `row` per completed clause,
   then `done` with the summary. First insight lands in ~10 s instead of minutes; the
   found/missing tally ticks up live; partial results survive a failure; and it
   *dissolves* the WKWebView timeout (bytes flow continuously). One change fixes the
   owner's complaint, the dead-air, and the probable timeout bug simultaneously.
2. **CONFIRMED: de-duplicate the grid's identical LLM calls (XS, no risk, no gate).**
   `evaluate_cell` calls `answer(column["question"], matter=matter, top_k, db_path)` —
   **the document is not an argument** (`grid.py:74`). Per-doc scoping happens *after*,
   as a citation filter (`grid.py:79`, `clauses.py:62-63`). So for D documents, every
   column makes **D byte-identical `answer()` calls**. Memoize one `answer()` per
   question per run and classify each row from the shared result: grid cost drops by a
   factor of D (5 docs: 100 calls → 20). Semantically identical by construction — the
   per-row classifier is already a pure filter over the same result.
3. **Interactive priority for review/grid (XS, no risk, no gate).** Call the same
   `activity` mark the chat route uses so background digest/ingest LLM work yields.
4. **Modest parallelism for the review loop (XS-S, measure first, no gate).** Reuse the
   grid's bounded `ThreadPoolExecutor` (`grid.py:98-101`, clamp ≤4 tested at
   `test_grid.py:102-121`). Caveat: the launcher doesn't set `OLLAMA_NUM_PARALLEL`
   (`launcher.py:57-58`), so Ollama may serialize the workers anyway, and raising it
   multiplies KV memory (num_ctx=8192) on 24 GB hardware. Benchmark before claiming a win.
5. **Persist + cache the finished review (S-M, low risk, no gate).** Store the result
   keyed (matter, doc-hash set, taxonomy version); render instantly on revisit with a
   visible "reviewed <date> over N documents — Run again" header. Turns a 4-minute tool
   into a 0-second tab after first run. Also the substrate for export (e).
6. **Doc-type-aware checklist (S, no gate) — designed but never wired.** Every taxonomy
   entry carries `doc_types` (`clauses.py:38`, tested `test_clauses.py:47-53`) and it is
   **never used to filter**: `extract_clauses` runs all 20 questions regardless
   (`clauses.py:112-121`). An NDA gets asked about insurance and audit rights — wasted
   calls and noise rows. Filtering by the document's type cuts cost and improves the
   read.
7. **Second-pass opt-out for checklist runs (S, gate required).** Would halve the cost of
   exactly the absent clauses, but `answer()` has no flag, so it means touching
   `answering.py` → full 63/63 + 9/9 gate. With streaming (option 1) the cost becomes
   visible rather than fatal; do this only if measured numbers still hurt.
8. **Smaller triage model: don't.** Already measured and rejected (D-79: qwen3.5:9b →
   46/63, 25 rejected claims, speed-neutral-to-worse). Documented dead end.
9. **Long-term: move the checklist to ingest time (L, no gate).** The matter digest
   already proves the architecture — background queue at ingest, span-verified facts
   persisted, LLM proposes / `verifier.locate_span` disposes (`digest.py:1-40`). A
   clause pass at ingest makes the Review tab render instantly from stored,
   span-verified rows, with "Run fresh" as the escape hatch. This is the shape that
   actually matches how attorneys work: the answer should be waiting for them.

## (e) Export / save design

Today: **the clause review has no export or save at all** (no endpoint in
`routes_clauses.py`; no button in `buildReview`, `app.js:2614-2657`). The grid has CSV
only, gated on `done`.

Recommended, consistent with patterns already shipped:

1. **"Copy review" button (XS).** Reuse the exact copy-cited-answer machinery:
   `answerPlainText` formats answer + numbered `[n] filename p.N: "span"` citations
   (`app.js:1242-1252`) and `copyPlainText` is the WKWebView-safe clipboard
   (`app.js:1257-1269`). A review memo is a concatenation: header (matter, date, summary
   counts), one block per clause (name, status, value, citations), and the existing
   not-legal-advice footer (`app.js:2432`). Zero new dependencies, same trust format the
   attorney already knows from chat.
2. **File download, Markdown + CSV (XS).** Client-side Blob exactly like `downloadCsv`
   (`app.js:2505-2512`) — no backend, no network. Markdown for the memo shape, CSV for
   the checklist-as-spreadsheet shape. Name it `review-<matter>-<date>.md`.
3. **Grid CSV fixes (XS):** include the cited span text (currently only `filename p.N`,
   `app.js:2497`); enable export on error with whatever cells completed; add the date and
   matter to the header row.
4. **DOCX/PDF: park.** Both need a new dependency (python-docx / reportlab), against the
   D-49/D-51 no-new-install discipline, and clipboard+Markdown covers the real workflow
   ("paste into the memo I'm writing"). Revisit only on attorney demand.
5. Persistence (d.5) is the save story; export without save still loses the run on quit.

## (f) Compare Documents grid — same audit

**Genuinely good, worth saying plainly:** the grid got the architecture the review tab
should have. SSE streaming with skeleton cells filling live (`routes_grid.py:43-58`,
`app.js:2448-2487`); bounded, clamped concurrency with a test proving the bound
(`grid.py:22-30`, `test_grid.py:102-121`); an explicit document picker that preserves
selection across refreshes (`app.js:2515-2555`); CSV export with correct quote-escaping
(`app.js:2500-2502`); cross-document citation-leak post-filter with unit *and* live
integration tests (`test_grid.py:90`, `test_grid_live.py:70`); the same never-false-accept
classifier as everywhere else, not a fork (`grid.py:20`); every model string escaped
before render (`app.js:2442`); sticky headers tested (`test_grid_ui.py:73`). The clause
classifier itself (`clauses.py:50-80`) is exemplary: found only with a span-verified
citation, refusal → advisory with zero citations, rejected spans → "not confirmed" never
"found" — each invariant unit-tested (`test_clauses.py:130-165`) and live-tested against
the eval store (`test_clauses.py:226`). Taxonomy provenance is handled honestly
(CUAD-informed, CC-BY attributed, own phrasing, tested `test_clauses.py:66-77`).

**Defects, beyond the shared ones above:**

1. **CONFIRMED correctness ceiling: matter-wide top-5 retrieval starves rows.** Each
   cell's `answer()` retrieves the top 5 chunks across the *whole matter*
   (`answering.py:395`, top_k=5) and then filters citations to the row's file
   (`grid.py:79`). With N documents in the matter, one column's single shared retrieval
   can only ever surface chunks from at most 5 documents — so **in a 6+ document matter,
   some rows are mathematically guaranteed to read "potentially missing" even when the
   clause sits verbatim in that document.** The doc-scoped clause review has the same
   flaw (`clauses.py:62-63` — post-filter, not scoped retrieval). "Potentially missing"
   as an artifact of retrieval competition, not document content, is the single biggest
   credibility risk on this tab: an attorney who spot-checks one false "missing" will
   stop trusting every "missing." Real fix = per-document retrieval scoping, which means
   a filename filter in `retrieve()` → touches the engine → **gate required** (M). Until
   then the honest mitigation is UI copy: "checked against the matter's most relevant
   passages" rather than implying an exhaustive per-document scan.
2. **PLAUSIBLE: a "found" cell's value text can describe a different document.** The
   `value` shown is the matter-wide `answer_text` (`clauses.py:69`); citations are
   filtered per row but the prose is not. Doc A's cell can display a sentence written
   about Doc B's clause, with Doc A's citation chip attached, whenever both were in
   context and at least one span located in Doc A.
3. **Backend capabilities the UI hides:** custom questions and clause subsets exist on
   the route (`routes_grid.py:26-28`) — the UI never exposes them; single-document clause
   review exists (`routes_clauses.py:25`) — `runClauseReview` posts matter only
   (`app.js:2420-2423`). Attorneys review *a contract*, not a matter-blob; the most
   natural unit of this tab's work is unreachable from the UI.

## Why an attorney would / wouldn't use this tab

**Would:** the checklist mirrors real playbook review; every "found" is a verifiable
page+span citation one click from the highlight surface; the missing-clause signal is the
part of contract review humans are worst at (you can't ctrl-F an absence).

**Wouldn't, today:** (1) 3-6 opaque minutes — a lawyer skims the contract themselves in
that time; (2) can't review one contract, only the matter; (3) results are disposable —
no save, no export, no history, so the work product evaporates; (4) generic 20-clause
list with no doc-type filtering and no way to add their own playbook questions; (5) if
finding #f.1 bites in a real multi-document matter, false "missing" rows kill trust in
the one signal the tab uniquely provides.

## Recommended order

1. Stream the review (d.1) — fixes wait, timeout, progress in one move; no gate.
2. Grid memoization (d.2) + interactive priority (d.3) — two XS, pure wins.
3. Copy/export (e.1-e.3) + persistence (d.5) — makes the output an artifact.
4. Expose doc-scoped review + custom questions (f.3) and wire `doc_types` (d.6).
5. Schedule the gated retrieval-scoping fix (f.1) as its own gated cycle; longer term,
   evaluate ingest-time clause extraction on the digest pattern (d.9).
