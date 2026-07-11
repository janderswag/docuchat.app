# docuchat adversarial product audit — 2026-07-10

Scope: repo `/Users/janderswag/legal-document-chat`, branch `main`, HEAD `9218c70` (release: derive
bundle version from appversion.py), on top of `ee0153c`/`c58478f` (v0.4.0 — matter digest: M-2).
Method: read `pipeline/static/app.js` (2473 lines), `app.html`, and every `routes_*.py` router;
started the real FastAPI server from source (`pipeline/api.py` via `.venv/bin/python api.py`) and
curled it live at `http://127.0.0.1:8000`; ran `answer()` directly against the seeded sample
matter's real KB store to time the daily-loop path end to end. No code changes, no commits, no
mutating POSTs against the running app (only idempotent GETs + one direct in-process `answer()`
call that touches no catalog state).

Voice: harshest-competent-staff-engineer-plus-product-person. Every claim below is grounded to a
file:line or a live request/response captured during this session.

---

## 1. First-run / day-1

**What works:** the desktop launcher (`desktop/launcher.py:425-477`) shows a branded splash
instantly, boots Ollama + the FastAPI server on a worker thread, then loads `/setup` → `/app`
(`launcher.py:453`). `/setup` (`pipeline/routes_setup.py`, `static/setup.js`) has a real SSE
progress bar for model downloads (`setup.js:101-141`, `event: progress` with `percent`), disk-space
preflight (`setup.js:60-64`), and never dumps a raw stack trace at the user. This part is genuinely
solid.

**What's rough:**

- **Root `/` is broken.** `pipeline/static/index.html:73` fetches `/eval/matters` on load; live:
  `curl http://127.0.0.1:8000/eval/matters` → `500 Internal Server Error`. Server traceback:
  `ValueError: Table 'chunks' was not found` (lancedb `open_table` on the separate **eval** store,
  distinct from the app's `.lancedb_kb`). The packaged desktop app never routes here (it goes
  straight to `/setup`/`/app`), so this doesn't hit a paying attorney — but it's the literal root
  URL of the open-source repo an engineer evaluating docuchat (the README's own stated audience)
  would hit by curiosity, and it 500s instantly. Cheap, embarrassing, easy fix.
- **First-run race between "seeded" and "usable."** `_seed_sample_matter` (`api.py:167-175`) and
  digest backfill (`api.py:153-155`, `digest.py:355` `backfill_async(initial_delay=20.0)`) both run
  async after startup. Live sequence observed: right after `/health` went green, `GET
  /matters/sample-matter/overview` returned `"building":{"done":0,"total":3}` and **zero**
  deadlines/timeline/parties; a same-moment direct query against the KB store failed with `Table
  'chunks' was not found` (the ingest queue hadn't finished either). ~20s later, digest showed
  `1/3` done and real deadline rows appeared. `routes_chat.py:58-62` correctly turns an
  not-yet-indexed matter into the honest D-30 refusal rather than an error, which is the right
  fallback — but the product experience for the very first suggested question
  (`/matters` → `suggested_questions: ["What is the monthly fee under the services
  agreement?", ...]`) can plausibly be "I could not find this in the documents" if the attorney
  clicks fast, which reads as broken, not "still working."
- **Silent privacy-feature failure at startup.** Server log (this run): `could not add Time
  Machine exclusion for /Users/janderswag/legal-document-chat/pipeline/.lancedb_kb`. Per
  `api.py:158-165` / the `data_protection` module's own docstring, this is by design
  ("failures log, never block startup") — but there is **no UI surface anywhere** (checked
  Settings view build code in `app.js`) that tells the attorney their Time-Machine-exclusion
  promise (a headline privacy claim in the README) silently didn't take on their machine.
- **Startup is ~10-12s wall-clock before `/health` is green** in this environment (encrypted-volume
  mount + model/embedder preload threads + Time-Machine exclusion attempt, `api.py:111-183`). The
  splash screen (`launcher.py:383-399`) covers this reasonably, so it's not a raw gap, but it stacks
  with the ~20s digest delay and the serial ingest queue below before a brand-new matter is fully
  "expert."
- Found a stray `pipeline/.kb_catalog.db.locked-20260710` (94 KB, untracked) sitting in the repo —
  the kind of leftover-from-a-previous-crash artifact that turns into a "docuchat won't start"
  support ticket. Worth checking `startup_recovery.py`'s self-heal path actually clears these, not
  just Keychain-key mismatches.

## 2. The daily loop

**Where it feels expert:** the matter overview (`routes_digest.py`, M-2) is the real differentiator
shipped in v0.4.0. Every fact row is span-verified, zero LLM calls at read time
(`routes_digest.py:8-9` docstring), and the confirm/dismiss UX
(`app.js:915-937` `deadlineRow`) is honest about what's machine-derived ("date as written —
confirm?") vs. attorney-owned ("confirmed by you"). Verified live: a direct `answer()` call against
the seeded matter returned a correctly-cited answer (`$12,500... [document: sample-services-
agreement.pdf, page: 1, ...]`) in 9.3s once indexing finished. Per the project's own git log, the
extractor is gated at "63/63 golden + G-DIG PASS" — real quality discipline, not vibes.

**Where it's hollow — the gap between "digest" and "matter":**

- A "matter" here is a document folder with LLM-extracted metadata. There is no case status/stage,
  no assigned attorney, no client contact record, no matter-level free-text notes field anywhere in
  `routes_matters.py` (35 lines — create/list/rename only) or the digest schema
  (`digest.py`/`routes_digest.py` — parties/amounts/terms/refs/dates only, all document-sourced).
  Nothing in the overview is attorney-authored except a confirmed date.
- **The single biggest expert-vs-hollow gap:** a confirmed deadline (`POST
  /matters/{matter}/facts/{fact_key}/review`, `routes_digest.py:63-73`) just sits in the in-app
  list. There is no calendar export anywhere in the codebase — `grep -n "ics\|calendar"
  static/app.js` matches nothing except connector *service labels* (Google/Outlook aren't even in
  the 28-connector catalog as calendar sources — see `app.js:1651+`). The app does the hard, novel
  part (find the deadline, quote the source, get the attorney to confirm the date) and then drops
  it at the exact moment it would prevent a missed-deadline malpractice claim.

## 3. Workflow dead-ends

Confirmed absent by direct grep of the entire 2473-line `app.js` plus the router set:

- **No copy/print/export of a chat answer.** The *only* `navigator.clipboard.writeText` call in
  the whole frontend is for the referral link (`app.js:2441`, inside `buildReferrals`). The chat
  answer renderer `window.renderAnswerHtml` (`app.js:1175-1199`) emits answer text + a confidence
  pill + source citations — no copy button, no "export to memo," no print affordance anywhere near
  it.
- **No calendar action on a confirmed deadline** (see §2). Not even a downloadable `.ics` — the
  server already has everything needed (`confirmed_date`, `label`, `filename`+`page` citation) in
  `overview()`'s `deadlines` array (`routes_digest.py:30-56`).
- **"Export" exists but means something else.** `app.js:739/778-779` wires a matter-level
  `<button id="matter-export">` to `window.open("/retention/" + slug + "/export")`, which hits
  `routes_retention.py`'s `GET /retention/{matter}/export` — a full-matter ZIP for legal-hold /
  disposition (`retention.export_matter`), not an answer or memo export. An attorney who wants "the
  three answers I just got, as a Word doc for the file" has no path; the only "export" button does
  something completely different (and heavier-weight).
- **No conflict check.** Zero matches for "conflict" anywhere in `app.js` or the router set — not
  even a stub. Given the product's own framing ("solo attorney," CLAUDE.md), this may be
  legitimately out of scope for v1, but it's the first thing a second attorney joining the practice
  would ask for.
- **No matter notes field**, confirmed by `routes_matters.py`'s thin surface (create/list/rename
  only — no notes/description column exercised by any route).

## 4. Trust surfaces

**Good, and worth calling out as good:** the confidence pill is explicitly labeled "Model
self-confidence (display only — does not affect citations)" in its own tooltip (`app.js:1193`), and
`answering.py:445`'s comment confirms verification is purely mechanical and never consults
confidence — this is an unusually honest design choice (most RAG products blur "the model sounds
sure" with "the citation is real"). The refusal path (`REFUSAL`, D-30) is wired through both `/chat`
and `/chat/stream` so an unindexed matter fails safe instead of hallucinating (`routes_chat.py:60-
62`).

**Where the app claims more than it currently proves, live:**

- The privacy claim ("nothing about you or your machine leaves it," Time-Machine exclusion) failed
  silently in this exact run (§1) with zero UI acknowledgment — a gap between the marketed privacy
  posture and what's actually verifiable from inside the app.
- The root demo page's own live self-check (`/eval/matters`, meant to prove "here are the matters
  you can query") 500s instead of demonstrating anything (§1) — the one surface whose entire job is
  showing the product working is the one that's currently broken.

## 5. Performance / robustness holes (from code + live timing)

- **Retrieval scale ceiling is documented in-repo and is bad news at "500 docs."**
  `retrieval.py:39-41`: *"(D-66 scale audit): 1.5s at 10k chunks, 15.6s + 4.7GB RSS at 100k,
  projected swap"* beyond that. A 500-document matter of real contracts (not 3 tiny synthetic PDFs)
  plausibly lands well past 10k chunks; the code's own comment says the next milestone past 100k is
  swapping — a genuinely bad failure mode on an attorney's laptop mid-question.
- **Both the ingest queue and the digest queue are single serialized daemon threads** —
  `ingest_worker.py:1-10` (explicitly replacing a prior 40-concurrent-thread design, D-68, for
  correctness) and `digest.py:317-321` (`matter-digest-worker`). That's the right correctness call,
  but it means a 500-document matter ingests **and then digests, one document at a time**, each
  digest pass being a real LLM call. Observed live: the 3-document sample matter took ~20s+ to reach
  `1/3` digest-done. At even 15-20s/doc for real contracts, a 500-doc matter's overview could take
  multiple hours to fully populate, during which the UI's own polling
  (`app.js:899`, every 5s) just shows "Building matter digest — N of 500 documents…" with **no ETA,
  no reordering/prioritization, no pause** — only a static counter.
- **Cold start is ~10-12s to `/health` 200** in this run (encrypted-volume mount + preload threads +
  the Time-Machine-exclusion attempt that itself failed and had to be caught) — acceptable behind
  the splash screen, but it compounds with the above before a *brand-new* matter is queryable.
- Upload path is reasonably guarded: 25 MB/file cap, allow-listed extensions
  (`routes_kb.py:29-32,67-74`) — no obvious abuse surface there.

## 6. The wow-factor question

**Recommendation: "Confirm deadline → Add to calendar."** A one-click `.ics` download (or a direct
Google/Outlook calendar link) generated server-side from an already-`confirmed` deadline row.

**Why this, argued from the product as it exists today, not a wishlist:**

1. The matter digest (M-2, v0.4.0) is the one feature in this codebase that isn't "RAG chat with
   citations" — every competent legal-AI demo has that now. Span-verified fact extraction with an
   attorney confirm/dismiss loop is the actual differentiator, and it's already built and gated
   (63/63 golden + G-DIG PASS per the git log).
2. Right now that feature's payoff dead-ends *inside the app* (§2, §3) — a confirmed date just sits
   in a list the attorney has to remember to re-check. The single highest-leverage, lowest-effort
   next step is also the one that matches how attorneys actually avoid malpractice: get the date
   into the calendar they already trust, not into a new app they have to remember to open.
3. All the data is already server-side and already flows through mechanical verification —
   `overview()`'s `deadlines` items (`routes_digest.py:30-56`) already carry `confirmed_date`,
   `label`, `filename`, `page`, and `span`. This is a small, additive feature (one route generating
   an `.ics` blob from data that's already computed and already trusted) with an outsized story:
   "docuchat read my engagement letter, found the renewal-notice deadline, I confirmed the date in
   one click, and it went straight into my calendar." That's the moment that converts "neat demo"
   into "I told my partner to install this."

---

Report path: `/Users/janderswag/legal-document-chat/docs/council/2026-07-10-reports/gaps-audit.md`
