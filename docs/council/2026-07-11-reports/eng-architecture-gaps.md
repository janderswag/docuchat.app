# Architecture & engineering gaps — principal-engineer audit

_Council 2026-07-11. Repo HEAD `4c4d5cc` (main == origin/main), v0.4.3 live. Read-only audit;
every claim cites file:line, verified in code this session — not from docs. Prior audits
(2026-07-07-reports/scale-audit.md, 2026-07-10-reports/gaps-audit.md, connectors-audit.md) were
read first; closed findings are verified closed below, not re-litigated. Watched-folders and
"Find in documents" UX detail is in the sibling report `eng-folders-find.md` (same council) —
this report stays on architecture and only adds what that one doesn't cover._

---

## (a) Prior-audit findings: actually fixed vs still open (verified in code)

### Verified FIXED

| Finding (audit) | Evidence it's fixed |
|---|---|
| Matter-allowlist full-store scan, unusable at ~90 docs (scale-audit #1) | `retrieval.py:33-55` — matter-column-only scan, cached by table version (`_MATTERS_CACHE`); measured ~10ms @100k per its own comment |
| Ingest ran on the request thread pool, starved /chat (scale-audit #2) | `ingest_worker.py:32-61` — one dedicated daemon worker + `queue.Queue`; uploads enqueue instantly |
| Zero ingest instrumentation (scale-audit #3) | `ingest_worker.py:93-108` per-stage `perf_counter` timings + `status()` snapshot (`:47-53`) |
| LanceDB never optimized (scale-audit #5) | `ingest_worker.py:123-130` (`OPTIMIZE_EVERY = 50`), `retention.py:114-116` |
| Connectors not bundled — 0 of 28 in the .app (connectors-audit #1) | `desktop/build_macos.spec:51` + `build_windows.spec:53` `collect_submodules("connectors")`; enforcement: `build_macos.sh:76-84` runs `desktop/smoke_packaged.sh` (asserts 28 services), `SKIP_SMOKE=1` is loud |
| Chat thread splitting on transient failure (gaps-audit / RUN_STATE) | `routes_chat.py:189-200` guarded persist ("must not abort the stream before 'done'"); `catalog.py:202` `PRAGMA busy_timeout = 5000` |
| Silent Time-Machine-exclusion failure (gaps-audit §1/§4) | `routes_settings.py:33-39` surfaces `app.state.data_protection` per-path results |
| Confirmed deadline dead-ends in-app, no calendar (gaps-audit §2/§6) | `routes_digest.py:31-90` `.ics` build (RFC 5545 escape/fold, attorney's date only); UI at `app.js:920-925` — note this fix site is where the `%27` pattern for (c) below was established |
| No copy of a cited answer (gaps-audit §3) | Copy-cited-answers shipped v0.4.1 (WKWebView-safe clipboard path per RUN_STATE; `navigator.clipboard` no longer referral-only) |
| First-run race: sample matter seeded but digest-empty (gaps-audit §1) | `sample_matter.py:173-178` digest-enqueues seeded docs; `digest.py:344-352` `BACKFILL_DONE` guard withholds the "stuck" verdict until the one-shot sweep ran |

### Still OPEN

1. **`GET /eval/matters` still 500s when the eval store is absent** (gaps-audit §1 "root `/` is
   broken"). `api.py:220-224` calls `known_matters()` → `embed_store.open_table` (`:97-99`)
   raises unhandled when the `chunks` table doesn't exist. `index.html:73-79` swallows it
   client-side (`.catch(() => {})`), so the page renders but the demo self-check silently shows
   nothing and the endpoint 500s for the curious engineer. Cheap fix: catch → `{"matters": []}`.
2. **Stray `pipeline/.kb_catalog.db.locked-20260710` still on disk** (gaps-audit §1).
   `startup_recovery.py` moves poisoned data aside but nothing ever ages/cleans asides.
3. **No ETA / prioritization / pause for large-matter ingest+digest** (gaps-audit §5).
   `ingest_worker.status()` / `digest.status()` expose queue depth + current doc only; the UI
   polls a static counter. The multi-hour-500-doc-matter scenario is still a blind wait.
4. **A matter is still only a document folder** (gaps-audit §2) — no notes/status/contact.
   Product decision, not engineering debt; unchanged.
5. **FTS staleness footgun is now LIVE, not dead code** (scale-audit §3 flagged it as
   "currently-dead"). `retrieval.py:72-79` builds the FTS index on first use;
   LanceDB's native FTS does not cover rows appended after build until an optimize pass, and
   optimize runs only every 50 ingests (`ingest_worker.py:30`). Since `/search` "Best match"
   (fts mode) and the anchor-fed hybrid arm (`retrieval.py:125-132`) are shipped surfaces, a
   freshly ingested document can be invisible to "Best match" search for up to 49 ingests.
   "Every mention" mode is unaffected. Fix: optimize (or FTS-index refresh) per-ingest or on
   search when store version changed; re-verify against `eval/SCALE_EVAL.md`.
6. **OAuth loopback-redirect infra still not built** (connectors-audit §2) — correctly
   owner-gated on registrations; no code exists (`grep redirect_uri` still empty).
7. **E-signature adapter still absent from the catalog** (connectors-audit §4 #5) — acknowledged
   in the handoff backlog.
8. **No timeout on any answering-path Ollama call** — `answering.py:166,234,411` are bare
   `urlopen(req)` (only `preload_model:192` has one). A hung Ollama blocks a request thread
   forever. Pre-existing and previously tolerable; clause review multiplies the exposure ×20
   per click (see b-R1). Caveat: this is INSIDE the frozen engine — fix must ride a full
   63/63-gated cycle, batched with other engine work.

## (b) Top architectural risks for the next phase

### R1 (highest): `POST /clauses/review` — 20 LLM generations inside one synchronous request

The owner's Review-tab complaint is structural, confirmed:

- `routes_clauses.py:35-54` is one blocking POST; `clauses.py:113-121` loops the full taxonomy —
  **20 clauses** (`data/clause_taxonomy.json`, counted) — calling `answer()` per clause. Each
  `answer()` = embed + retrieve + a full qwen3:14b generation (~18 tok/s measured, scale-audit
  §4 → ~15-25s each). **A review is a 5-10 minute blocking request.**
- **Contention, both directions.** Clause review never calls `activity.mark_chat()` (callers:
  `routes_chat.py:58,164,189`, `routes_transcripts.py:125` only) — so ingest/digest workers see
  the system as idle and run their own LLM/embedding work concurrently against the same
  single-lane Ollama; conversely, a chat question asked mid-review queues behind up to 20
  pending generations. The review makes the whole app feel dead.
- **No cancellation, no double-click guard, no progress.** `app.js:2412-2436` shows a static
  "this can take a moment" and awaits one fetch (no timeout, `api()` at app.js top). Clicking
  Run twice interleaves two 20-call loops. Navigating away wastes the burn.
- **No persistence, no export.** Grep confirms: zero clause tables in `catalog.py`, zero
  save/export in `routes_clauses.py`. The result lives only in the DOM. This is the owner's
  "can't save or export" — accurate.
- **`doc_types` is carried but never used.** `clauses.py:38,65` copies the field into each row;
  nothing filters the checklist by the matter's actual document types — all 20 questions run
  even when half can't apply. Free 2× speed-to-insight sitting unused.

**The fix shape already exists in this repo, engine untouched:** `routes_grid.py:36-58` streams
per-cell SSE with skeleton fill-in. Clause review should become the same: per-clause SSE
(first insight in ~20s instead of last insight at 8 min), an in-flight guard, interactive
priority marking, doc_types pre-filter, a persisted review-run row in the catalog (keyed
matter + doc-set hash → enables "last reviewed" and re-open), and a docx export reusing the
`routes_transcripts.py:153` Word-table writer. All orchestration around `answer()`; the frozen
answer path is not modified; no golden gate required.

### R2: single-process coupling + hand-rolled workers

The packaged app is ONE process: uvicorn daemon thread + Cocoa run loop
(`launcher.py:152-168`, restart-marker watcher `:398-425`). Consequences the next phase strains:

- Any long synchronous request dies silently on update-relaunch/quit. Today all long work is
  read-only (safe to kill); the moment a long request WRITES (matter export/import bundle is on
  the backlog), a mid-flight kill corrupts. **Rule to adopt now: anything >10s becomes a queued
  background job with catalog-persisted state, never a request.**
- This is the **third** hand-rolled worker (ingest `ingest_worker.py`, digest `digest.py:317-343`,
  and review would be the fourth) — each with its own queue, status dict, and yield policy. The
  "background job center" has been queued since v0.2.0 (RUN_STATE) and dropped from the 07-11
  handoff; its absence is re-felt every cycle. Generalize before the fourth copy.

### R3: no central Ollama scheduler as LLM consumers multiply

Chat, digest extraction, clause review, and the comparison grid (`grid.py` clamp 4 workers) all
funnel into one local Ollama, num_ctx 8192 (`answering.py:83`, `digest.py:45`). The only
priority mechanism is the advisory `activity.py` timestamp, honored by exactly two consumers,
for exactly one signal (chat). Also, `mark_chat` fires at stream start and end only
(`routes_chat.py:164,189`) — a >10s generation lets `chat_recent()` lapse mid-answer and
background work resumes against it. The interaction matrix grows with every feature. A small
shared "LLM lane" (priority: interactive > review/grid > digest, one module, no engine change)
future-proofs this.

### R4: memory & catalog concurrency — currently OK, watch two things

- Resident models ≈ 12GB of 24GB (9.3GB qwen3:14b + 1.2GB bge-m3, keep_alive 30m both paths).
  LanceDB scans are mmap'd; the allowlist cache is a frozenset of names. **No memory bomb found
  post-D-68.** The real risk is minimum-spec attorney hardware: setup preflight checks disk
  only (`setup.js:60-64`), not RAM — a 16GB machine will swap with models + Docling + WKWebView.
  Add a RAM preflight/warning before wider distribution.
- Catalog contention is patched (busy_timeout 5000, `catalog.py:202`), not solved: no
  `journal_mode=WAL` anywhere (grep), so the default rollback journal lets writers block
  readers across 4+ threads. 5s stalls under load remain possible. Cheap investigation
  (WAL × SQLCipher compatibility check), low urgency.

## (c) Apostrophe-in-href bug — CONFIRMED; scope is larger than the handoff note

**Mechanism:** `esc()` DOES escape apostrophes (`app.js:25-28`). The hole is URLs built with
`encodeURIComponent` — which leaves `'` raw — interpolated into **single-quoted** HTML
attributes. The digest overview already fixed its own instance with `.replace(/'/g, "%27")` and
a comment naming the bug (`app.js:920-925`). Three sites still have it:

1. **`citationThumb` — `app.js:1145-1152`**: `href='…span=' + encodeURIComponent(c.span)` and
   the `src='…'` of the thumbnail. `c.span` is verbatim document text; apostrophes ("party's",
   "lessor's") are ubiquitous in legal prose, so **this is a live correctness bug today**: any
   citation whose span contains `'` truncates the attribute → broken highlight link/thumb.
2. **`highlightUrl` — `app.js:1174-1176`**: consumed by `injectChips` (`:1183-1199`, the inline
   source chips) and the numbered sources list (~`:1206`). Same truncation.
3. **Search hits — `app.js:1732-1734`** ("Find in documents"): `href` embeds
   `encodeURIComponent(snippet.slice(0,80))`. Same class; the handoff note doesn't list this one.

**Exploitability, honestly scoped:** after the quote breaks, remaining span characters are
still percent-encoded except `!'()*-._~` — space and `=` are encoded, so arbitrary
event-handler/tag injection is NOT reachable through `encodeURIComponent` output alone. Grade
this **Important (broken citation links on ordinary legal text) with residual parser-differential
risk in WKWebView**, not Critical XSS.

**Scoped fix (~1 hour, UI-only, no gate):** one helper (or the established inline pattern)
`url.replace(/'/g, "%27")` applied at the three URL builders above, plus a regression test
rendering a citation whose span contains an apostrophe and asserting the `href` round-trips
intact. Do not "fix" by switching esc() or rewriting attribute quoting — surgical, matching
the overview's proven pattern.

## (d) Engineering gaps, ranked risk × effort

1. **Apostrophe-in-URL, 3 sites** — high impact (silently broken citation links — the trust
   surface), trivial effort. Do first. (c)
2. **Clause review re-architecture** (SSE per-clause + in-flight guard + doc_types filter +
   activity marking + persisted runs + docx export) — the owner's #1 pain; ~2-4 days; grid and
   transcript-export patterns are reusable; zero engine risk. (b-R1)
3. **Native folder picker bridge** (pywebview `js_api`/`expose` + `FOLDER_DIALOG`, text-input
   fallback for dev/smoke) — ~0.5-1 day; full spec in sibling report `eng-folders-find.md` §1b.
4. **Background job center** — generalizes the three (soon four) hand-rolled workers into one
   jobs table + status UI; ~3-5 days; pays down R2/R3 and gives §a-open-3 its ETA surface.
5. **FTS staleness on ingest** — ~0.5 day + scale-eval re-verify. (§a-open-5)
6. **`/eval/matters` 500 + locked-file aside cleanup** — ~1 hour of polish. (§a-open-1/2)
7. **Ollama call timeouts in `answering.py`** — small code, but inside the frozen engine:
   batch into the NEXT gated engine cycle (with M-1 query rewriting), never a lone gate run.
8. **WAL investigation; RAM preflight in setup** — cheap, pre-distribution hygiene. (b-R4)

## (e) Handoff-backlog sanity check (docs/prompts/2026-07-11-session-handoff.md)

- **Architecturally premature: "Fact router (digest steers retrieval)."** It requires a full
  63/63 + G-AGG gate cycle, and M-1 query rewriting (also gated) sits above it. Running two
  separate engine-gate cycles is waste; **batch all engine-touching work (query rewriting +
  fact router + the answering.py timeouts from (d)7) into one gated cycle**, and only after the
  non-gated owner-pain items above. Nothing in the owner's council notes asks for the router.
- **Newly urgent and MISSING from the backlog:** (1) clause-review async/persist/export — the
  owner's #1 concern isn't on the list at all; (2) the native folder picker; (3) the background
  job center (present in the v0.2.0 queue, silently dropped from this handoff — restore it as
  the umbrella for #1).
- **Under-scoped as written:** the apostrophe item names `injectChips/renderAnswerHtml` only —
  it's three sites including search hits (`app.js:1732-1734`); fix all in one diff.
- **Correctly sequenced:** OAuth flow after owner registrations; matter export/import (with the
  R2 caveat: build it as a background job from day one, never a long request); Windows build
  (owner-blocked); extractor v5 (label quality, not trust).
- **"Digest backfill retry-on-Ollama-recovery" — agree, and it's cheap.** Verified: a failed
  extraction correctly leaves the doc unstamped (`digest.py:280-300`) but only the ONE-SHOT
  startup sweep (`digest.py:374-395`) retries — an Ollama hiccup mid-session leaves docs
  undigested until the next app restart. A periodic re-sweep of `_stale_doc_ids` closes it.
- **Owner concern #2 (connector value), architecture verdict:** the ingest spine is sound and
  uniform — every connector import flows through `connsync.py:60-80` (managed copy → catalog →
  serialized ingest → chunk/embed → digest), lands in Unfiled with provenance, and a notetaker
  transcript IS a draggable, chat/search/digest-visible document (`.vtt/.srt` get page:line,
  `routes_kb` allowlist). What limits value is not the pipe but scheduling depth (30-min poll,
  no backfill windows/filters) and the un-built OAuth tier — a product-research question for the
  connectors seat, not an architecture defect.
