# Council: Review & Compare, and How Documents Actually Arrive — 2026-07-11

Seven independent reports feed this council: four adversarial engineering audits grounded in this
repo at HEAD (Review & Compare tab; connector ingestion value; watched folders + find-in-documents;
architecture & gaps), and three market/design research sweeps (why attorneys adopt or reject
contract-review tools; which integrations drive retention in legal tech; the design bar for
conservative desktop buyers). Reports in `docs/council/2026-07-11-reports/` — every engineering
claim carries file:line evidence, every market claim a source URL. This document is the synthesis:
seat verdicts, convergent findings, the owner's five questions answered directly, and the ranked
plan for this session. Seats weighted per the owner: attorneys and practice staff speak first.

Owner brief this council answers: why the Review & Compare tab takes so long and can't be saved,
how attorneys would actually use it and why they wouldn't; how connectors/APIs actually bring
value (including whether a notetaker transcript becomes a real draggable document); whether
watched folders is necessary and why it appears broken; what "Find in documents" is for and how
to make it discoverable; and the overall progress, gaps, and adoption picture.

---

## 1. Where we stand (context)

**v0.4.3 live as Latest.** Three releases across one day (2026-07-10/11): the matter digest with
attorney-confirmed deadlines (v0.4.0, gated 63/63 + 9/9 + G-DIG); connectors actually shipping in
the bundle + the packaged-app smoke gate + deadline .ics + copy-cited-answers + the chat-thread
fix (v0.4.1); launcher-owned restart after update + the slash palette (v0.4.2); palette anchored
below the input per the owner's design call (v0.4.3). The answer engine is UNTOUCHED since the
v0.4.0 gate. Both demands from last council's attorneys (Maria's .ics, the copy-cited-answer)
shipped and are acknowledged by the seats below.

**What this council found, in one sentence:** the discipline that fixed the bundle has not yet
reached the features — the Review tab is a 3-6 minute synchronous POST that likely never survives
WKWebView's ~60s no-bytes timeout in the packaged app, produces work product that cannot be
saved, exported, or billed, and its retrieval shape mathematically guarantees false "potentially
missing" rows in 6+ document matters; meanwhile the two ways documents actually arrive at a firm
(email attachments, the scanner folder) are respectively unsearchable (F2) and hidden behind a
typed-POSIX-path interface.

Key evidence anchors (verified in code by the reports):

- `routes_clauses.py:35` — one blocking POST; `clauses.py:113-121` loops 20 sequential `answer()`
  calls; absent clauses fire the refusal second pass, so missing clauses cost double.
- WKWebView fetch rides a ~60s no-bytes timeout; `/clauses/review` sends zero bytes until done —
  PLAUSIBLE that nearly every packaged-app run dies client-side while Ollama burns on
  (eng-review-compare §b). Must be verified in the built .app first.
- No save, no export, no persistence: zero clause tables in `catalog.py`, zero export endpoints.
- `grid.py:79` / `clauses.py:62-63` — matter-wide top-5 retrieval, post-filtered per document:
  in a 6+ doc matter some rows are guaranteed false "potentially missing." CONFIRMED.
- The fix pattern already ships in this app: the Compare grid streams per-cell SSE with skeleton
  fill (`routes_grid.py:36-58`, `app.js:2557-2593`) and none of the rework touches the frozen
  engine (verified: `clauses.py`/`grid.py` are pure consumers of `answer()`).
- Gmail F1 (`gmail.py:203` — import capped at the OLDEST 500 UIDs forever; sync silently dead on
  real mailboxes) and F2 (`extractors.py:70-100` — attachment content never extracted despite
  "attachments included" copy). Provenance stored but never shown (F3, `connsync.py:77`).
- Watched folders: free-text path input (`app.js:2124`), conflated two-condition error
  (`app.js:2157`), no recursion (`watchers.py:98`), filename-only dedupe (`watchers.py:104`),
  `except Exception: pass` on the daemon loop (`watchers.py:121-122`). Native picker feasible via
  the pywebview bridge (~25 lines, launcher has no `js_api` today).
- Apostrophe-in-URL: three live sites break citation links on ordinary legal text
  (`app.js:1145-1152, 1174-1176, 1732-1734`) — the digest overview already established the fix
  pattern (`app.js:920-925`).

## 2. Seat verdicts (each seat deliberately critical; attorneys and staff first)

**Maria — solo litigator (returning seat). Verdict: you closed my loop last council and then
built a Review tab that reopens every wound — four minutes of dead air producing work product
that cannot be saved, exported, or billed, on a checklist that can be mathematically wrong.**

Last time I demanded .ics and copy-cited-answers; both shipped, credit where due. Now hold Review
& Compare to the same bar and it fails three ways. First, it isn't work product: no save, no
export, results evaporate on quit (eng-review-compare (c)). An unsaved review is not billable and
not defensible in the file when the client second-guesses me. Second, it probably never even
arrives — the WKWebView 60s no-bytes timeout likely kills nearly every run while Ollama burns for
minutes (report (b)). Third, and this is the malpractice one: matter-wide top-5 retrieval with
post-filtering guarantees false "potentially missing" rows in 6+ doc matters (grid.py:79). A
checklist that invents missing indemnification clauses is worse than no checklist; I will rely on
it exactly once. The Vals data says we scoped to the winning side (Q&A/extraction), so the tab is
worth saving — but only streamed, persisted, and exported as a red-flag .docx I can put in the
file.

Connectors: transcripts and email are the two families that touch my practice, and email is
broken where it matters — attachments are name-listed, content unsearchable (F2), and Gmail
permanently stalls at the oldest 500 (F1). My key documents ARE attachments. Fix those before
adding vendor 29. Suggest-then-confirm filing matches the confirm-every-date ethos; keep that
line.

Watched folders: KEEP, redesign — it's my scanner path. Native picker, split the error message,
show "last checked / files added." Typing POSIX paths is disqualifying.

Find in documents: KEEP separate. Exhaustive every-mention with true totals is how I check
privilege and coverage; never merge it into the generative path. Rename it "Every mention" and
link it from citations.

The ONE build: convert /clauses/review to the grid's SSE pattern with persistence and .docx
export. One move kills the timeout, the dead air, and the evaporating work product.

**Rosa — managing partner, 6-attorney firm (returning seat). Verdict: v0.4.1 fixed the empty
bundle I flagged, but the same disease — promises the packaged app doesn't keep — has moved into
the features themselves.**

Credit earned: the smoke gate exists, 28 services list in the real DMG, and the Unfiled-drag flow
is the right suggest-then-confirm shape the entire DMS industry converged on. That's
institutional progress, not luck.

Now the disease's new addresses. **Review & Compare:** a firm cannot buy this tab. A 3-6 minute
synchronous POST that probably dies at WKWebView's ~60s idle (eng-review-compare F2) means the
packaged app may literally never finish a review while Ollama burns for minutes — test the built
.app before anything else, that's the standard I hold. And with no save or export, the result
isn't work product: not billable, not delegable to an associate, gone on quit. Attorneys'
benchmark tools export cited tables to Word/Excel; ours evaporates. The 6+ doc false-"missing"
ceiling is disqualifying for firm matters, which are never two documents. **Connectors:** value
is real only where honest. Gmail's silent 500-UID dead end (F1) breaks sync on every real firm
mailbox, and "attachments included" while attachment content is unsearchable (F2) is the
empty-bundle pattern in content form — the card says one thing, the product does another. Fix
F1+F2+provenance badges; present a Core Four (Email, Meetings, Folders, PM); stop growing the
28-card long tail — CRM dumps are negative value. **Watched folders:** KEEP, redesign — it IS our
storage connector while Drive/Dropbox sit "Coming," but my staff will never hand-type a POSIX
path; native picker plus a live "last checked / 3 files added" row, no training required. **Find
in documents:** KEEP, don't merge — every-mention search is paralegal bread and butter; rename it
and kill the engineer-speak dropdown.

**The ONE build:** the streamed, persisted, exportable clause review (grid's SSE pattern + .docx
red-flag report). It converts the tab from a demo liability into billable work product, and it
needs no gate. Windows remains my standing blocker.

**David — transactional attorney, data-loss averse (returning seat). Verdict: I would not run
this on a 40-page MSA today, because even when it finishes I am left holding nothing I can bill,
file, or defend.**

Run it as my daily driver: I paste in the MSA, click Run, and get one static line for 3-6 minutes
while the server burns Ollama inside a blocking request that WKWebView probably kills at 60
seconds anyway (routes_clauses.py:34, app.js:2417). In those same minutes I can skim the contract
myself. Worse: I cannot review *the contract*, only the matter blob, even though the single-doc
route exists and the UI never calls it (routes_clauses.py:25 vs app.js:2420). And in a 6+
document matter, matter-wide top-5 retrieval mathematically guarantees false "potentially
missing" rows (grid.py:79) in the ONE signal I cannot ctrl-F myself, absence. One false "missing"
I spot-check and I never trust the tab again. Then it evaporates on quit: no save, no export, no
history. Unsaved review is not work product; it is a preview I cannot attach to the file to prove
my diligence. CoCounsel and Harvey export cited tables to Word/Excel as table stakes; the
red-flag report format we should emit already exists.

What survives: span-verified citations plus local-only match my two real anxieties, and Vals says
extraction/Q&A is the side AI actually wins. The grid architecture is genuinely good; the review
tab just never got it.

Positions: **Connectors**: fix Gmail's 500-UID cap and attachment blindness before adding any
vendor; email attachments ARE my documents. **Watched folders**: keep, native picker, split that
insulting error message; it is my scanner path. **Find in documents**: keep separate, rename to
"Every mention"; exhaustive substring search is a different legal act than asking a model. **The
one build**: stream the clause review over the grid's existing SSE pattern, persist the finished
run, and add copy/Markdown export. One move kills the dead air, the timeout, and the data loss.
Nothing else this session until that ships.

**Patricia — tech-skeptic solo (returning seat). Verdict: last council I gave you your one
sentence; this council you have three features that fail my five-minute test in three different
ways, and one of them fails it while quietly burning my laptop for six minutes.**

Review & Compare: I click Run, a gray line says "this can take a moment" (app.js:2417), and
nothing happens for 3-6 minutes. In the packaged app it likely dies at ~60s with "Failed to
fetch" while the server keeps working (eng report, WKWebView timeout). A normal person concludes
the app is broken, force-quits, and tells a colleague it's broken. And if I wait it out? The
result evaporates when I close the app; no save, no export, nothing I can bill or file. Analysis
I cannot keep is a party trick. The grid already streams; the review must too, and it must
persist and export to .docx. Not negotiable.

Connectors: real files landing in Unfiled that I drag onto a matter is a story I actually
understand. But "your email is searchable" while attachments, the only part of my email that
matters, are name-only (F2)? That's a broken promise wearing a checkmark. Fix F1/F2 before adding
vendor 29.

Watched folders: KEEP, but today it is broken by my definition. A matter is selected, I click the
button, and it scolds me to "choose a matter." It asks a lawyer to type a POSIX path. Native
folder picker, honest error messages, and a visible "Watching, last checked 12s ago, 3 files
added" line. Nothing less.

Find in documents: KEEP, don't merge. "Every mention, exhaustive, no AI" is a sentence I trust
MORE than chat. But buried fourth in a scroll with a mode dropdown, I'd never find it. Rename it,
promote it, link it from citations.

The ONE build: convert Contract Review to streaming per-clause results with save and export. It
fixes the wait, the timeout, the double-click, and the evaporating work product in a single move,
and it never touches the frozen engine.

**Aisha, legal-tech reviewer (returning seat). Verdict: you built the only architecture in this
category that answers attorneys' two biggest fears, then wrapped its flagship tab in the single
most disqualifying UX in the field; ship the deliverable, not the panel.**

Review & Compare, honestly: Vals VLAIR times Harvey and CoCounsel sub-minute and names the
5-minute tool the laggard; our 3-6 minute synchronous POST (routes_clauses.py:35) that likely
dies at WKWebView's ~60s fetch timeout while Ollama keeps burning is worse than the laggard, it's
a tab that appears broken. We will never win raw latency against cloud GPUs, so stop competing on
it: progressive per-clause delivery plus persistence is the category's real lesson (Harvey's
cells are individually re-runnable and citable), and the SSE pattern already exists in our own
grid. Export is not a convenience, it's the definition of work product: CoCounsel emits
Excel/Word, Harvey client-ready .docx with flags preserved. A review that evaporates on
navigation is not billable and not defensible. Our grid maps almost 1:1 onto the Bloomberg
red-flag report; we just don't emit it. What survives my steelman: Vals shows AI beats lawyers at
Q&A/extraction (94.8 vs 70.1) and loses at redlining; we scoped, correctly, to the winning side,
and span-verified plus local answers the 43% accuracy-distrust and 37% security objections no
cloud vendor can. But a fixed checklist is not a playbook; make it editable or experienced
attorneys will call it a toy.

Connectors: email-to-matter filing is THE retention integration (ndMail, iManage,
suggest-then-confirm matches our ethos), yet F1/F2 mean Gmail labels over 500 messages never
finish and attachments, the actual documents, are unsearchable. Fix those before marketing email
at all; present a Core Four, not a 28-card wall. Watched folders: KEEP and redesign (native
picker, split the conflated error, live status); it is our real cloud-storage story. Find in
documents: KEEP, rename "Every mention," repoint /find at it; exhaustive non-LLM mention counts
are a diligence primitive no competitor's chat offers.

One build this session: convert /clauses/review to streaming per-clause SSE with persisted runs
and .docx/.xlsx red-flag export. One move kills the timeout, the dead air, the evaporation, and
the no-deliverable gap, without touching the frozen engine.

**Elena — staff paralegal (intake, filing, document wrangling) (NEW SEAT). Verdict: you built a
filing room where documents can't arrive the way documents actually arrive, and the tray I'd
live in is unreadable.**

Documents reach a firm three ways: email attachments, the scanner folder, client-portal
downloads. Docuchat is broken or hostile on all three. Email: F2 means "attachments included" is
false; the extractor lists attachment filenames only (extractors.py:70-100), and the attachment
IS the document - the envelope is nothing. F1 means any label over 500 messages silently never
finishes and never syncs new mail (gmail.py:203). Scanner: watched folders is the right idea with
a developer's interface - I will not hand-type an absolute POSIX path (app.js:2124), the
conflated error blames me for a matter I already picked (app.js:2157), no subfolder recursion
kills every scan-to-dated-folder scanner (watchers.py:98), and filename-only dedupe means a
corrected re-scan of contract.pdf is silently never ingested (watchers.py:104). That last one is
a filing-integrity hazard, not a nit. **Keep watched folders** - it's the only scanner and
synced-drive path (app.js:2147-2148) - but native picker, split guard, heartbeat, recursion
honesty.

Unfiled triage: connectors dump rows with zero provenance despite source_json holding date,
sender, participants (connsync.py:77, read by nothing). Fifty anonymous rows is not a tray I can
file from. The industry pattern is suggest-then-confirm filing chips; that's my job made faster,
and it fits attorney-confirms. CRM firm-wide dumps (F6) are negative value; skip that family.

**Find in documents: keep, never merge.** Exhaustive counted mentions (routes_search.py:112-130)
is a paralegal sweep - names, amounts, defined terms. Rename it "Every mention," promote it,
repoint /find at it.

Review tab: not my surface, but no save/export means I can't run it overnight and hand the
attorney results - so it can't be delegated, so it won't be used.

**One build: email that tells the truth - F1 uncap + F2 attachments as child documents, plus
source_json badges on Unfiled rows.** Everything else is decoration if intake lies.

**Jonas — principal product designer, ex-FAANG (NEW SEAT). Verdict: the Ledger is a real design
system; the product's worst moment is hiding inside its most important feature, and you already
own the fix.**

The warm-paper/Newsreader/gold foundation is distinctive and slop-free — protect it. But Contract
Review fails the bar on behavior: a multi-minute synchronous run whose entire feedback is one
static muted line (`app.js:2417`), a Run button that's never disabled so an anxious double-click
silently fires a second Ollama run (`app.js:2412-2436`), no cancel, and a result that evaporates
— no save, no export, while the sibling grid has CSV (`app.js:2505`). That's not a speed problem,
it's a granularity problem: render the taxonomy as skeleton rows instantly (endpoint exists,
`routes_clauses.py:28`), stream per-clause over SSE exactly like `runGrid` (`app.js:2557-2593`),
persist, export .docx. The pattern already ships in this app; Review just doesn't use it.
Attorneys will use this tab only when partial results appear in seconds and the artifact survives
— Harvey's per-cell progressive tables are the category proof.

Positions. **Watched folders: KEEP, redesign the affordance.** A typed POSIX path (`app.js:2124`)
plus a conflated error (`app.js:2157`) is the single most "web page, not Mac app" moment; one
native-picker button via the pywebview bridge and a live status row ("Watching · checked 12s ago
· 3 files added") fixes it. **Find in documents: KEEP, do not merge** — it's exhaustive
enumeration, the opposite mechanism to chat; rename it "Every mention," give it its own
destination, repoint `/find`, and add a "See every mention of X" link from citations.
**Connectors:** value dies at the black box; every import must land as a visible outcome ("14
transcripts → Unfiled") with source glyphs in tables and citation chips — provenance is your
design language, make connectors speak it. And fix the cool-blue `#eef3ff` drag tint
(`app.js:470`); it's the one place the Ledger breaks.

**The ONE build: convert Contract Review to the grid's streaming skeleton pattern, with
persistence and export.** Everything else this session is polish; that one changes whether the
feature exists.

**Priya — head of engineering (returning functional seat). Verdict: the architecture is sound
everywhere except the one place the owner clicks most, and the fix is already sitting in this
repo; build clause review as the first tenant of a real job runner, not a fourth hand-rolled
worker.**

Review & Compare: useful in shape, disqualifying in mechanics. Twenty sequential answer() calls
inside one blocking POST (routes_clauses.py:35, clauses.py:113-121) is 5-10 minutes of dead air
that likely dies at WKWebView's ~60s idle while Ollama keeps burning; it never marks activity, so
digest and ingest workers pile onto the same single-lane Ollama mid-review; Run has no in-flight
guard, so a double click doubles the burn; nothing persists, nothing exports. None of this
touches the frozen engine. The grid's SSE pattern (routes_grid.py:36-58) fixes wait, timeout, and
progress in one move; add a persisted review-run row, doc_types pre-filter, and .docx export via
the transcript writer. Also fix the memoization waste (grid.py:74, D identical calls per column)
and flag the matter-wide top-5 retrieval ceiling for the next gated engine cycle, because
guaranteed false "missing" rows in 6+ doc matters is a trust bug, not a speed bug.

Connectors: the ingest spine is uniform and correct (connsync.py:60-80), but F1 (Gmail stuck at
oldest 500 UIDs) and F2 (attachments unsearchable) mean email, the highest-value family, is
broken in practice. Fix those before adding vendor 29.

Watched folders: KEEP, redesign. It is our only cloud-drive and scanner path. Native picker via
pywebview js_api (~25 lines), split the conflated guard (app.js:2157), show last-scan status.
Half a day.

Find in documents: KEEP, do not merge. Exhaustive zero-LLM mentions is the opposite mechanism
from /find's generative path; rename it, repoint /find at it.

The ONE build: clause review as a streamed, persisted, exportable background job, implemented on
a generalized job runner that ingest and digest migrate onto next. That retires R1 and R2
together, and the smoke gate stays mandatory on the release.

Sequenced before it: the apostrophe-in-URL fix (app.js:1145, 1174, 1732), one hour, live broken
citation links on ordinary legal text. Fact router stays parked; batch all engine-gated work into
one cycle.

**Sam — ethics & security officer (returning functional seat). Verdict: the ingestion spine is
trustworthy; the edges of it — silent matter-bound sync, invisible provenance, and an export path
pointed at a known false-"missing" defect — are where privilege goes to die.**

Earned praise first: connector credentials are keyvault ciphertext only (catalog.py:315,
connsync.py:91), pulled items land DEK-encrypted on the single audited ingest path
(connsync.py:60-80), and the never-compute-a-date line held even as transcripts full of spoken
dates now enter the digest. Hold that line forever.

**Review & Compare:** stream it, persist it — but persist runs inside the encrypted catalog, not
loose JSON. Export is table stakes (mkt report §d), and I won't block attorney-initiated copies
of their own work product. I will block this: retrieval is matter-wide top-5, so in 6+ doc
matters some "potentially missing" verdicts are mathematically false (grid.py:79). Exporting that
as a clean red-flag memo is a manufactured malpractice vector. Export ships with per-clause
verification status and a scope caveat, or after the retrieval fix. Non-negotiable.

**Connectors:** real value, one ethics defect. Unfiled-default with human drag-to-matter is the
correct privilege boundary — suggest-then-confirm is where the whole industry landed
(mkt-connector report). But connect-time matter binding plus silent 30-minute sync
(routes_connections.py:26-27, connsync.py:151-171) auto-files a mislabeled Gmail label into a
client matter forever, unreviewed. And F3 makes it worse: provenance is stored and never shown,
so a 50-item Unfiled dump can't be triaged — you cannot ethically file what you cannot identify.
F6's firm-wide CRM dumps are cross-client contamination as a feature; filter or pull the card.

**Watched folders: KEEP, redesign.** Native picker, split the guard — and note a folder bound to
one matter, pointed at Downloads or a shared scanner tray, is a contamination machine; offer
Unfiled as a target. `except Exception: pass` (watchers.py:121-122) on an ingestion daemon is a
security surface, not a style nit.

**Find in documents: KEEP.** The exhaustive-mentions sweep IS the privilege-review workflow; the
`/find` name collision actively misleads — rename it.

**ONE build:** the Review rework — streamed, persisted encrypted, exported *with verification
caveats* — plus the source_json badge on Unfiled rows as its guardrail rider.

## 3. Convergent findings (what independent seats and reports hit without coordination)

1. **The Review rework is unanimous — all nine seats name the same ONE build.** Convert
   `/clauses/review` to the grid's per-clause SSE streaming (skeleton rows from the existing
   taxonomy endpoint, first result in ~10-20s), add an in-flight guard + cancel, persist finished
   runs, and export. It simultaneously kills the 3-6 minute dead air, the probable WKWebView ~60s
   timeout (bytes flow continuously), the double-click double-burn, and the evaporating work
   product — and it never touches the frozen answer engine (verified: clauses/grid are pure
   consumers of `answer()`; no golden gate required). The market report independently lands on
   the same shape: docuchat cannot win raw latency against cloud GPUs, so it must win on
   progressive delivery + persistence (Harvey's per-cell tables are the category proof), and
   export is the definition of work product, not a convenience (CoCounsel → Excel/Word, Harvey →
   .docx; unsaved review = not billable, not delegable, not defensible).
2. **The false-"missing" retrieval ceiling is a trust defect, not a speed defect — and export
   must not launder it.** Matter-wide top-5 retrieval post-filtered per document (grid.py:79,
   clauses.py:62-63) guarantees false "potentially missing" rows in 6+ doc matters, in the one
   signal an attorney cannot ctrl-F (absence). Five seats (Maria, Rosa, David, Priya, Sam) called
   it independently; Sam makes it a release condition: export ships with per-clause verification
   status and a scope caveat ("checked against the matter's most relevant passages," never
   implying an exhaustive per-document scan), or after the retrieval fix. The real fix
   (per-document retrieval scoping) touches the engine → batch into the next full 63/63 gated
   cycle, never a lone gate run.
3. **Email is the highest-value connector family and it is broken exactly where the value is.**
   F1: Gmail import is permanently capped at the OLDEST 500 UIDs, so labels over 500 messages
   silently never finish and new mail never syncs (gmail.py:203). F2: "attachments included" is
   false — attachment content is never extracted, and the attachment IS the document
   (extractors.py:70-100). F3: rich provenance (sender, date, participants) is captured and never
   shown, making the Unfiled tray untriageable (connsync.py:77). Every attorney seat + the
   paralegal + both connector reports converge: fix F1+F2+F3 before any 29th vendor; present a
   Core Four (Email, Meetings, Folders, Practice Management) instead of a 28-card wall; CRM
   firm-wide dumps (F6) are negative value and an ethics hazard.
4. **Watched folders: unanimous KEEP, unanimous redesign.** It is the product's only scanner and
   synced-cloud-drive path while Drive/Dropbox/OneDrive sit OAuth-gated — the storage-connector
   story for this cycle, and (per the market report) the most differentiated connector docuchat
   has, currently its least legible. Owner's confusion fully reproduced from code: the matter WAS
   selected; the free-text path was empty; the conflated guard blamed both (app.js:2157). Fix:
   native folder picker via the pywebview bridge (~25 lines, text input as no-bridge fallback),
   split the guard, live heartbeat ("Watching · checked 12s ago · 3 files added"), subfolder
   honesty, log instead of `pass`, and Unfiled as a target per Sam.
5. **Find in documents: unanimous KEEP, never merge into chat — it just needs a true name and a
   visible home.** It is the product's only exhaustive, zero-LLM, true-total surface (the
   privilege-sweep / every-mention diligence primitive no competitor's chat offers), mechanically
   the opposite of the generative path — and the `/find` slash command currently routes to the
   OPPOSITE mechanism. Rename the panel "Every mention," promote it out of the Hub's fourth
   scroll position, repoint `/find` at it, replace the mode dropdown with labeled choices, and
   cross-link "See every mention of X" from chat citations.

Also converged, below the headline: the apostrophe-in-URL bug breaks citation links on ordinary
legal text TODAY at three sites (Priya sequences it first; ~1 hour); every long operation must
land as a visible outcome with source glyphs (Jonas's "connectors must speak provenance" = Elena
and Sam's F3 badge); and the WKWebView timeout must be verified in the built .app before being
treated as fact (Rosa's standard, the known browser-QA-misses-WKWebView class).

## 4. The owner's questions, answered directly

### Q1. Review & Compare: gaps, real usage, speed-to-insight, and why it would NOT be useful

**Where the gaps are (all verified in code):** (1) One synchronous blocking POST runs 20
sequential `answer()` calls, 3-6 minutes typical — and absent clauses cost DOUBLE because every
refusal fires the second-pass retrieval (eng-review-compare §a). (2) The packaged app likely
never receives the result: WKWebView's ~60s no-bytes timeout kills the fetch while the server
burns on (PLAUSIBLE — verify in the built .app first). (3) Nothing persists and nothing exports:
no save endpoint, no history, no copy button; the result lives only in the DOM. (4) The UI can
only review the matter blob; the single-document route exists (`routes_clauses.py:25`) and is
never called. (5) `doc_types` filtering is designed and never wired — an NDA gets asked about
insurance clauses. (6) The retrieval ceiling: guaranteed false "potentially missing" rows in 6+
doc matters. (7) No in-flight guard, no cancel, no activity marking (digest workers compete with
the review for the one Ollama).

**How attorneys would actually use it:** not for negotiation redlining — the category's Word-
add-in redline flow (Spellbook, DraftWise, Gavel) is a different genre docuchat correctly does
not attempt, and Vals shows AI losing to lawyers there anyway. The honest genre is the
**portfolio/diligence review**: "what's in this matter's contracts, what's missing across them" —
the doc-x-clause grid is the same format as Harvey's Vault review tables, CoCounsel's Review
Documents, and Gavel's web batch mode, and its memo form is the Bloomberg red-flag issues report.
The absence signal (missing clauses) is the one thing a human can't ctrl-F. Vals VLAIR says AI
decisively beats lawyers at exactly this (Q&A 94.8 vs 70.1, extraction, summarization) — the tab
is scoped to the winning side.

**Speed-to-insight:** stop competing on total latency (sub-minute cloud norm is unreachable on
local inference); win on time-to-first-result and persistence. Concretely, in order: stream
per-clause SSE with instant skeleton rows (first insight ~10-20s); memoize the grid's D-identical
calls per column (5 docs: 100 calls → 20, semantically identical by construction); wire
`doc_types` (skip inapplicable questions); expose single-document review; persist finished runs
(a re-opened review costs 0 seconds); mark activity so background work yields. A second-pass
opt-out would halve absent-clause cost but touches the engine — gate-cycle item only if measured
numbers still hurt after streaming.

**Why attorneys would NOT use it (the steelman, condensed from mkt-attorney-adoption §E):** it
produces analysis, not work product (no redline, no memo, terminates in a panel); it's not in
Word, the category's revealed habitat; it's slow in a sub-minute category with the worst failure
mode (nothing until everything); the quality ceiling is real (frontier cloud tools lose to
lawyers at review; a local model sits below them — a false negative here is a malpractice vector,
and a prudent attorney re-reads the contract anyway, making the tab a step added, not saved); a
generic 20-clause checklist tells an experienced attorney what they already know — the firm's
playbook is the value (make the checklist editable or it's a toy); no save/export = not billable,
not delegable, not defensible; and many solos lack the contract volume to care. What survives:
span-verified citations + local-only answer the two measured adoption blockers (43% accuracy
distrust, 37% security) no cloud vendor can, and the fixes are all workflow-shaped, not
engine-shaped.

### Q2. Connectors: how each family's API actually brings value

**The notetaker-transcript question, answered concretely: yes.** A Fireflies/Zoom/Read AI
transcript is pulled as a real file (`.vtt` with speaker voice-tags, `.txt`/`.md` fallback),
written DEK-encrypted into the matter tree, catalogued with provenance, and pushed through the
SAME ingest path as a drag-dropped PDF: extract → chunk → embed → digest facts. It lands in
Unfiled as a visible row the user clicks and DRAGS onto a matter, exactly like any document.
Speaker turns are preserved as `[HH:MM:SS] Speaker: text` lines — "who said what when" is
searchable, citable, and feeds the digest. This is the best-executed detail in the connector path
and the family to demo (eng-connectors-value §1). The market wedge is real and current: generic
notetakers cannot file to matters (Zapier-only), AI-notetaker privilege risk is front-page legal
news, and "the copy the AI searches never leaves your desk" is a pitch no cloud vendor can make.

**How ingestion works for every family:** adapter lists items → seen-ledger filters → each fresh
item fetched as (filename, bytes, provenance) → managed encrypted copy + catalog row with
`source_json` → the one serialized ingest worker → chunks, embeddings, digest facts → cited
answers. Manual Import button plus optional 30-minute polling sync. One spine, no forks
(connsync.py:60-80) — the architecture verdict is that the pipe is sound; the leaks are
family-specific.

**Family value ranking, delivered today:** (1) AI notetakers — HIGH, end-to-end working; (2)
meeting platforms (Zoom/Webex) — MEDIUM-HIGH, same path, honest preconditions; (3) email —
MEDIUM delivered / HIGH promised: the design (label = matter, raw .eml, read-only IMAP) is
exactly right and it is the family attorneys need most, but F1+F2 cut delivered value roughly in
half — fix them and email becomes #1; (4) transcription services — MEDIUM, niche (depositions);
(5) notes/docs/work-management — LOW-MEDIUM, weak matter affinity floods Unfiled; (6) Slack — LOW
(files only; "threads" don't exist here and nothing corrects the user's mental model); (7) CRM —
LOW-to-NEGATIVE (firm-wide dumps of numeric-ID notes; ethics hazard per Sam); (8) cloud storage —
LOW by vendor mismatch: the storage attorneys use is OAuth-gated "Coming," and the honest bridge
is a watched folder pointed at the sync folder — which is why fixing watched folders IS the
storage story this cycle.

**What the industry teaches (mkt-connector-value):** email-to-matter filing is THE retention
integration in legal tech; the winning UX everywhere is suggest-then-confirm with learned
suggestions, thread stickiness, a visible "Filed" badge, and background filing — which happens to
be docuchat's attorney-confirms ethos already. Copy those; consciously reject write-back sync,
full-mailbox mirroring, Zapier glue, channel-binding, and silent auto-file. Daily-use families
are boring and few (email, the meeting record, e-sign artifacts, file storage); most of the 28
cards are résumé lines, not retention. Depth on four beats breadth on 48.

### Q3. Watched folders: verdict and redesign

**KEEP — it is load-bearing, not redundant.** It is the only path for scanner scan-to-folder and
for Dropbox/Drive/OneDrive synced folders while OAuth storage sits "Coming," with zero network
code; the catalog copy itself points users here. Killing it orphans the cloud-drive story.

**Why it appeared broken:** the matter picker WAS pre-filled; the free-text path was empty; the
two-condition guard emitted one blaming message ("Choose a matter and enter a folder path") in a
13px line (app.js:2157). The button never "does nothing" in code — but the perceived result of
the most natural click is a scolding for something already done. The deeper defect is the
affordance: it asks an attorney to hand-type an absolute POSIX path.

**Redesign (smallest set that makes it self-explanatory):** (1) native macOS folder picker via
the pywebview bridge — expose `create_file_dialog(FOLDER_DIALOG)` over a `js_api` (~10 lines
launcher, ~15 lines app.js; text input survives only as the no-bridge dev/smoke fallback); (2)
split the guard and name the field, focus the offending control; (3) heartbeat — extend the
folders endpoint with `last_scan` and `files_added` and render "Watching · checked 12s ago · 3
files added" (this also surfaces the disposed-matter dead row); (4) honesty riders: recurse one
level or say "subfolders are not watched," log instead of `except: pass`, note the filename-only
dedupe hazard (a corrected re-scan of contract.pdf is silently never ingested — Elena's
filing-integrity flag), and offer Unfiled as a target per Sam (a matter-bound folder pointed at a
shared scanner tray is a contamination machine). Add the entry point on the matter detail page
where the matter is already known. Not recommended: fsevents/watchdog, per-file feeds — poll-15s
is fine at this scale.

### Q4. Find in documents: verdict

**KEEP, never merge into chat.** Three things share the word "find" and two of them are opposite
mechanisms: the panel is an exhaustive, zero-LLM scan of every chunk with TRUE totals ("this term
appears exactly 37 times, here is every one"), while chat and the `/find` slash command are top-k
generative retrieval that structurally cannot be exhaustive. The panel is the product's only
zero-hallucination enumeration surface — the privilege-sweep / every-mention-of-a-name workflow —
and it is core-principle aligned (every result a real chunk). Its problems are purely legibility:
the name collides with `/find` (which does the opposite), it sits fourth in a filing-page scroll,
and "Best match" vs "Every mention" is engineer vocabulary. Fix: rename to **"Every mention"**,
give it its own destination (nav slot or top of matter detail), repoint `/find` at it, replace
the dropdown with two labeled choices ("Every mention — exact text, counted" / "Best match —
ranked, for when you don't know the exact wording"), and add the "See every mention of 'X'" link
from chat citations — that one link teaches the relationship at the moment of need. One related
engineering note: FTS staleness means a freshly ingested doc can be invisible to "Best match" for
up to 49 ingests (retrieval.py:72-79 + OPTIMIZE_EVERY=50); "Every mention" mode is unaffected.

### Q5. Overall: progress, gaps, adoption, architecture

**Progress is real and verified:** ten prior-audit findings confirmed FIXED in code (matter-scan
cache, ingest worker, smoke gate, thread-splitting, TM surface, .ics, copy-cited, first-run race,
among others). The ingestion spine is uniform and sound; the digest pattern (precompute, verify
mechanically, render instantly) is the correct architecture and the Compare grid proves the team
can ship the right streaming shape. The market lane holds: only free local-first
verified-citation product; span-verified + local answers the two top measured adoption blockers.

**Why attorneys would adopt:** time recovered on repeat work, "senior attorney over the
shoulder," zero context-switch, and — uniquely ours — the privacy/verification story with
receipts. **Why they wouldn't:** the Review tab's current mechanics (this council's centerpiece),
intake that lies (F1/F2), features that require typing POSIX paths, no Word-native output, no
Windows, and low contract volume for many solos. **Architecture risks, ranked (Priya/eng-gaps):**
R1 the blocking review (this session); R2 single-process + third hand-rolled worker (rule
adopted: anything >10s becomes a queued background job — never a long request — before matter
export/import ships); R3 no central Ollama priority lane as LLM consumers multiply; R4 RAM
preflight + WAL investigation before wider distribution. Engine-touching items (per-doc retrieval
scoping, answering.py timeouts, M-1 query rewriting, fact router decision) are BATCHED into one
future gated cycle — never lone gate runs.

## 5. Prioritized session plan (owner-approval encoded)

**Mission statement:** *The Review tab becomes work product: it streams, it survives, it exports
with honest caveats — and the two ways documents actually arrive (email, the scanner folder)
stop lying.*

Discipline riders on every move: adversarial review after each task (nine-for-nine hit rate
stands); the packaged-app smoke gate is mandatory on the release (never SKIP_SMOKE); the answer
engine is untouched (every move below is orchestration/UI — verified no-gate); never compute a
date; no AI slop (Jonas's blacklist §d is now canon: no spinners-with-quips, no confidence
scores, no sparkles, no cool-blue drift); nothing added for its own sake.

**Move 0 — Verify the WKWebView timeout in the built .app (XS, ~30 min).** Run a real clause
review in the packaged app and observe the ~60s failure. It is PLAUSIBLE, not CONFIRMED, and it
sets the urgency narrative for Move 2. (Rosa's standard; the known browser-QA-misses-WKWebView
class.)
> **Executed 2026-07-11 — REFUTED.** Empirical probe on this machine (pywebview/WKWebView,
> same-origin fetch against a local server): a fetch receiving ZERO bytes for 300s completes
> normally (`elapsed_ms: 300014`, body delivered), and a chunked trickle stream also survives.
> The packaged app does eventually receive the blocking review; the defect is pure UX
> (minutes of dead air, no persistence, no export, no cancel), not a transport failure.
> Move 2 scope unchanged. Probe: scratchpad `wkwebview_timeout_probe.py` / `probe_one.py`.

**Move 1 — Apostrophe-in-URL fix, all three sites (XS, ~1 hour).** `app.js:1145-1152, 1174-1176,
1732-1734` — citation links break TODAY on ordinary legal text ("party's"). Apply the overview's
proven `%27` pattern + a regression test. Surgical; do first. (Priya; trust surface.)

**Move 2 — THE BUILD: Review & Compare rework (M, ~2-4 days).** All nine seats. Scope:
(a) convert `/clauses/review` to per-clause SSE on the grid's exact pattern — skeleton rows from
`GET /clauses/taxonomy` render instantly, rows fill in taxonomy order, live found/missing tally;
(b) Run → Cancel swap + in-flight guard (no double-burn); (c) mark interactive activity so
digest/ingest yield; (d) wire `doc_types` pre-filter (free ~2x on inapplicable clauses);
(e) expose single-document review (route exists, UI never calls it) — attorneys review a
contract, not a matter blob; (f) persist finished runs in the ENCRYPTED catalog keyed (matter,
doc-hash set, taxonomy version), with a visible "reviewed <date> over N documents — Run again"
header; (g) export: copy-cited (reuse `answerPlainText`/`copyPlainText`), Markdown/CSV client-side
Blob, and .docx red-flag report via the existing transcript Word-table writer
(`routes_transcripts.py:153` — no new dependency; confirm during build, else park .docx per
D-49/D-51 and ship copy+Markdown); (h) **Sam's non-negotiable:** every export carries per-clause
verification status and the scope caveat ("checked against the matter's most relevant passages")
until the retrieval-scoping fix ships; (i) grid memoization — one `answer()` per question per run
(grid.py:74; 5 docs: 100 calls → 20, identical by construction); (j) grid CSV fixes (span text,
export-on-error, header metadata).

**Move 3 — Email that tells the truth + the provenance rider (S-M, ~1-2 days).** Elena's ONE
build, Sam's guardrail rider, every attorney's precondition for the email family: (a) F1 — uncap
Gmail by excluding seen UIDs before capping or tracking max-UID cursor; (b) F2 — extract
attachments as child documents through the existing `_ALLOWED` gate (or, minimum, correct the
card copy — but build the real thing); (c) F3 — source badge + date + participants on Unfiled and
Hub rows from the already-stored `source_json`, source glyphs in citation chips (Jonas: "14
transcripts → Unfiled" as a visible import outcome); (d) F4 — pass `last_sync` as `since` (one
line; saves Fireflies Free from quota self-DoS). Explicitly NOT this move: vendor #29, CRM
filters (park the family), Slack threads.

**Move 4 — Watched folders redesign (S, ~0.5-1 day).** Native folder picker via pywebview bridge
with text-input fallback; split the conflated guard + focus the field; heartbeat row ("Watching ·
checked 12s ago · 3 files added") via `last_scan`/`files_added`; subfolder honesty (recurse one
level or say so); log instead of `except: pass`; Unfiled as a target option; entry point on
matter detail. Note the bridge is invisible to the headless smoke path — assert bridge presence
in `smoke_packaged.sh` or record it as a manual gate item.

**Move 5 — "Every mention" legibility (S, ~0.5 day).** Rename the panel; own destination;
repoint `/find`; labeled mode choices; "See every mention of 'X'" link from chat citations.
Zero engine contact.

**Move 6 — Ledger integrity sweep (S, ~0.5 day, only if the night allows).** Drag-over tint
`#eef3ff` → `--accent-soft`; status-tint tokens in `:root`; promote repeated inline styles to
classes (`.panel-title`, `.field-err`). (Jonas #4/#5 — protects the design system; mechanical.)

**Release:** ship as v0.5.0 through the FULL gate — targeted tests per move, packaged smoke gate
(now also asserting the review SSE endpoint streams), signed/notarized/stapled, Latest. Expect
63/63 byte-identical since the engine is untouched; verify anyway.

**Definition of done:** Jake opens the built app, runs a review on the sample matter, sees the
checklist skeleton instantly and rows filling within seconds, cancels one run and re-runs, quits
the app, reopens, finds the review still there, exports it with the caveat line — then connects
Gmail on a 1,000-message label and watches it actually finish, with attachments searchable and
every Unfiled row wearing its source badge — then clicks "Choose a folder to watch" and gets a
real macOS dialog.

## 6. Explicit non-goals (queued, not forgotten)

- **The engine-gated batch** — per-document retrieval scoping (the false-"missing" real fix),
  answering.py Ollama timeouts, M-1 query rewriting, fact-router decision: ONE future gated
  63/63 cycle, deliberately not this session.
- **The generalized background job runner** (Priya's framing): the review rework is built
  job-shaped (persisted state, cancellable) but the full runner + ingest/digest migration is a
  next-cycle build — see Open decision #1.
- OAuth connector flows — still owner-registration-gated (Clio, Google, Microsoft, Read AI,
  NetDocuments).
- Windows build (owner box + Azure signing), matter export/import (must be a background job from
  day one per R2), editable checklist/playbook (Open decision #3), e-signature adapter,
  cross-matter "due this week," jurisdiction retention layer.
- CRM family investment, Slack thread ingestion, any 29th connector, suggested-matter filing
  chips (the ndMail-style ranking — right idea, next cycle, after F3 badges prove the tray).
- DOCX/PDF export via NEW dependencies (only the existing transcript writer path is in scope).
- Fact router: no seat and no owner note asked for it; stays parked.

## 7. Open decisions for the owner

1. **Job runner now or next?** Priya wants the review built as the first tenant of a generalized
   job runner (~+3-5 days, retires R2/R3); every other seat's shape is the minimal SSE conversion
   (~2-4 days). Council recommendation: minimal-but-job-shaped this session (persisted runs,
   cancel), full runner as the FIRST item of the next engineering cycle when ingest/digest
   migrate onto it. Your call if you'd rather pay once now.
2. **.docx export dependency check.** If the transcript Word writer doesn't cleanly produce the
   red-flag report shape, do we ship copy+Markdown only (no new installs, D-49/D-51) or approve
   python-docx? Attorneys asked for .docx by name.
3. **Editable checklist (the playbook question).** Aisha: "a fixed checklist is not a playbook;
   make it editable or experienced attorneys will call it a toy." The route already accepts
   custom questions (routes_grid.py:26-28). In scope for Move 2 as a minimal "add your own
   question" row, or next cycle?
4. **Connect-time matter binding + silent 30-min sync (Sam's ethics defect).** Options: (a) new
   synced items always land in Unfiled with a suggested-matter chip (pure suggest-then-confirm);
   (b) keep matter binding but add a visible per-sync review step; (c) keep as is with a louder
   warning at connect time. Sam recommends (a); it costs the "zero-touch" story.
5. **Catalog presentation: Core Four.** Regroup the 28 cards under Email / Meetings / Folders &
   Files / Practice Management with the long tail collapsed ("More services"), and pull or filter
   the CRM cards until F6 is fixed. Approve the demotion pass?
6. **The `/find` repoint** changes a shipped slash command's behavior (from composer template to
   navigation). Approve, or keep `/find` as-is and name the panel something else?
7. **Windows** remains Rosa's standing blocker — unchanged, awaiting your box + signing.

### Owner decisions (recorded 2026-07-11, before session start)

1. **Job runner: NOW.** Priya's shape wins — build the generalized background job runner this
   session with the review rework as its first tenant (retires R2/R3). Accepted scope impact:
   Move 2 grows to ~5-7 days total.
2. **.docx export: council default.** Use the existing transcript Word writer; if it cannot
   produce the red-flag report shape, ship copy+Markdown/CSV and park .docx (no new dependency
   without a separate approval).
3. **Editable checklist: persona recommendation (Aisha).** Include the minimal "add your own
   question" row in Move 2 (the route already accepts custom questions, routes_grid.py:26-28).
   Full playbook editing stays next-cycle.
4. **Sync binding: Sam's (a).** Synced items always land in Unfiled with a suggested-matter
   chip — pure suggest-then-confirm.
5. **Catalog: Core Four demotion approved** (Email / Meetings / Folders & Files / Practice
   Management; long tail collapsed; CRM cards pulled until F6 is fixed).
6. **/find repoint: approved.**
7. **Windows: owner begins after this session ships** (owner box + Azure signing).

## 8. New seats note (keep or drop)

- **Elena (staff paralegal) — KEEP.** She was the only seat who audited intake as a job rather
  than a feature list, and she found the two hazards no one else did: the filename-only dedupe
  that silently drops corrected re-scans (a filing-integrity defect, not UX), and the
  no-recursion kill of every scan-to-dated-folder scanner. The paralegal is also the actual
  daily operator of Unfiled triage and Every-mention sweeps — surfaces the attorney seats
  delegate. Distinct, load-bearing perspective.
- **Jonas (principal product designer) — KEEP.** The owner's design bar is load-bearing and now
  has a seat that speaks it with file:line evidence. His reframing of the Review problem as
  granularity-not-speed became the council's consensus mechanic, and his AI-slop blacklist (§4
  of mkt-design-bar) should be treated as standing canon for every future surface. Retain both;
  the council's returning-seat continuity (Maria/Rosa/David/Patricia holding the product to
  their prior demands) is visibly working and the two new seats filled the intake and design
  blind spots it had.
