# Design Bar Report — Senior Product Designer, 2026-07-11 Council

Role: design research + prescription against the owner's bar (senior-FAANG quality, instantly legible to a non-technical attorney, zero AI-slop). Sources: current UI code (`pipeline/static/app.css`, `app.html`, `app.js`), web research on reference tools and loading-state UX. All file:line references verified against the working tree today.

Headline: **docuchat's visual foundation ("The Ledger" — warm cream, Newsreader serif, IBM Plex Sans, gold accent) is genuinely distinctive and already avoids the big AI-slop tells.** The debt is not aesthetic, it is *behavioral*: the app's slowest, highest-stakes operation (contract review) has the app's weakest feedback design, and two utility features (watched folders, find-in-documents) use developer affordances instead of attorney affordances. Fixing five specific debts closes most of the gap.

---

## (a) What reference-quality desktop tools do that earns conservative buyers' trust

Studied: Linear, Things 3, Craft, Superhuman, iA Writer, DEVONthink, and the respected legal tools (Spellbook, CoCounsel, Harvey).

**1. One idea per surface.** Things 3 and iA Writer never put two jobs on one screen. Craft's editor shows the document and nothing else. Trust for a conservative buyer is legibility: "I can see everything this screen does." docuchat's Chat view now has this (empty-state greeting → pinned composer, the industry pattern, already implemented at `app.css:106-152`). The Document Hub does not — it is four unrelated jobs in one scroll (see debt #3).

**2. Opinionated typography instead of decoration.** iA Writer and Craft are trusted because the *type* is the design — a real serif for content, a workhorse sans for chrome, and almost no other ornament. docuchat already has this exact system (Newsreader for headings/answers, IBM Plex Sans for UI, `app.css:3-19`). Protect it; the risk is dilution via inline styles (debt #4), not absence.

**3. Status is a first-class visual language.** Linear's core trust move is that every object has a legible state (backlog/todo/in-progress/done) rendered identically everywhere. docuchat has the beginnings (`.status.ready/parsing/queued/failed`, `app.css:91-96`; `.clause-badge`, `app.css:185-188`) but the tint colors are hand-copied hex in six+ places (debt #5), which is how a status language decays.

**4. Provenance = the product, for legal buyers.** Spellbook wins attorneys by living inside Word (zero workflow change); CoCounsel wins by citation-backed answers tied to Westlaw. The common thread: **attorneys trust tools that show their work in the attorney's own terms (page, clause, source), never a score or a vibe.** docuchat's span-verified citation chips and "not confirmed ≠ found" honesty (`app.js:2401-2408`) are exactly the right instinct — this is the app's competitive design asset. Every new surface must inherit it.

**5. Native-feeling mechanics.** Superhuman and Things earn "professional" through OS-native behaviors: real file dialogs, real keyboard access, no web-form facsimiles of OS features. A free-text path input for folder watching (debt #2) is the single most "web page, not Mac app" moment in docuchat today. DEVONthink's *indexed folders* is the canonical reference: you pick a folder with the system dialog, and the folder thereafter appears as a live object with item counts and sync state — never a typed path. ([DEVONthink docs](https://www.devontechnologies.com/apps/devonthink), [community discussion of indexed folders](https://discourse.devontechnologies.com/t/indexed-folders/49218))

---

## (b) Long-running operations: keeping trust through a multi-minute local-LLM run

Research consensus ([NN/g on skeletons vs progress bars vs spinners](https://www.nngroup.com/videos/skeleton-screens-vs-progress-bars-vs-spinners/), [Eleken](https://www.eleken.co/blog-posts/progress-indicator-ux), [Userpilot](https://userpilot.com/blog/progress-bar-ui-ux-saas/), [AWS agentic-AI lens on streaming/TTFT](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentperf02-bp04.html), [AG-UI event lifecycle](https://docs.ag-ui.com/concepts/events)):

- **< 3s:** nothing or a skeleton. **3–10s:** determinate progress. **> 10s:** progress + *what is happening* + ideally partial results. Contract review on local Ollama is minutes → it is squarely in the "show work as it happens" regime; a static "this can take a moment" line is the wrong class of indicator by two categories.
- **Users judge perceived latency, not total time.** Visible progress roughly doubles willing wait time (22.6s vs 9s median in the cited study). Time-to-first-*result* is the metric to optimize, not time-to-done.
- **The strongest pattern for AI runs is streamed intermediate structure**: show the full checklist as skeleton rows immediately (the user sees the *shape* of the deliverable), then fill each row as its clause completes, with a "N of 24 clauses · checking Indemnification…" line. This is precisely ChatGPT Deep Research / agent-UI practice (StepStarted/StepFinished), and — critically — **docuchat already ships this exact pattern in the Compare grid** (`buildGridSkeleton` `app.js:2448`, SSE cell fill `app.js:2584-2586`, shimmer skeleton `app.css:202-204`). The design prescription is not new invention; it is *make Contract Review use the pattern its sibling tab already has*.
- **Never block the run button silently.** During a multi-minute run the button must become a visible in-progress state with a working Cancel. Today `clause-run` is never disabled (`app.js:2412-2436`) — an anxious double-click launches a second full Ollama run, which reads as a hang.
- **Progressive disclosure of the deliverable, not entertainment.** No spinners with rotating quips, no fake percent. For an attorney, the trustworthy wait experience is *the checklist visibly being worked through in order* — the digital equivalent of watching an associate go clause by clause. Skeleton rows in taxonomy order, filled top to bottom, deliver that; the taxonomy is already served separately (`GET /clauses/taxonomy`, `routes_clauses.py:28-31`) so the skeleton can render before the first token.
- **A minutes-long artifact must persist.** Anything that costs minutes to produce and is gone on tab-switch violates the effort-reward contract. The review needs save-per-matter + re-open + export (the grid has CSV at `app.js:2505`; the clause review has nothing).

**Why attorneys might NOT use the Review tab today (direct answer to owner note #1):** (1) minutes of dead air with no progress, no cancel, no partial output — feels broken; (2) the result evaporates — can't save, export, or hand to a client file; (3) one fixed generic checklist — a real estate attorney and an M&A attorney need different lists, and there's no way to see *which* clauses will be checked before burning minutes; (4) output is a flat list, not a work product — attorneys think in "issues to raise," so found-with-citation items and potentially-missing items should be separable/exportable as a memo-shaped artifact. Speed-to-insight fix order: stream per-clause (perceived), persist results (economic), let the user scope to one document — the API already accepts `doc_id` (`routes_clauses.py:25`) but the UI never exposes it.

---

## (c) Making utility features self-explanatory without adding chrome

**Watched folders** (owner note #3). The current UI is a free-text path input + button (`app.js:2124-2125`) and a combined error string ("Choose a matter and enter a folder path") that fires even when only the path is missing (`app.js:2157`) — the owner hit exactly this. Prescription, DEVONthink/Lightroom watched-folder pattern:
1. **One button: "Choose a folder to watch…"** opening the native macOS dialog. The app is pywebview/WKWebView; `webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)` exposed over the existing JS bridge gives a real OS picker. Kill the text input entirely (keep it only as a hidden fallback if the bridge is unavailable).
2. **The folder becomes a live object row**, not a table of paths: folder name (basename, path as secondary text), matter chip, and a status that says what the feature *does* — "Watching · checked 12s ago · 3 files added" — instead of the current binary watching/missing pill (`app.js:2110-2112`). A status row that shows *work done* is the feature's own explanation.
3. **Is it necessary?** Yes — it is the local-first answer to cloud-drive sync (scanner output, Dropbox/Drive synced folders) and the explanation copy at `app.js:2117-2121` is already excellent. The feature is right; only its affordance is wrong. It should also be reachable from the matter detail page ("Watch a folder for this matter"), where the matter is already known and the two-input confusion cannot occur.

**Find in documents** (owner note #4, `app.js:445-455`). What it is: exhaustive, non-AI passage listing ("every mention, not a top-5") — the complement to chat, and for attorneys a *primary* task ("show me every reference to the indemnity cap"). Relationship to chat: chat answers, Find enumerates; the two should cross-reference. Prescription without new chrome: (1) it already has a slash entry (`/find`) — good; (2) move it out of the Hub's bottom panel to its own destination (either a "Find" nav item or the top of the matter detail page — an attorney "goes to the matter, then searches it"); (3) rename the mode dropdown values — "Every mention" / "Best match" is good copy, but the panel title should carry the promise: **"Every mention"** with subtitle "List every passage that matches — no AI, just your documents."; (4) in chat answers, the citation footer can link "See every mention of X" to seed it — that single link teaches the feature's existence at the moment of need. No new surface area, three relocations and one link.

**Connectors** (owner note #2, design angle only): the catalog rows are already Granola-quality (`app.css:273-304`). The missing design piece is **post-import legibility**: after an import lands, the user must see *what arrived and where* ("14 transcripts → Unfiled") as a visible, clickable outcome, or the connector feels like a black box. Imported items should carry a small source glyph (Zoom/Gmail/etc.) in Hub tables and in citation chips — provenance is the app's design language and connectors should speak it.

---

## (d) AI-slop blacklist — specific to docuchat

Grounded in the current slop literature ([925 Studios' tells](https://www.925studios.co/blog/ai-slop-design-tells), [Impeccable's slop list](https://impeccable.style/slop/), [smoothui](https://smoothui.dev/blog/ai-design-slop), [why purple gradients dominate](https://prg.sh/ramblings/Why-Your-AI-Keeps-Building-the-Same-Purple-Gradient-Website)) plus this app's specific risks:

1. **Never Inter/indigo/violet, never a blue-to-purple gradient, never dark-mode-purple chat.** The Ledger's warm paper + gold is the brand; any cool-toned addition reads as pasted-in. (One already slipped in: the drag-over tint is an off-palette cool blue `#eef3ff`, `app.js:470` — see debt #5.)
2. **No emoji anywhere in UI copy, ever.** Empty states speak in the attorney's language ("No watched folders yet."), not "📂 Nothing here yet!". Current copy is clean; keep it that way. (Also owner-standing rule: no em-dashes in copy.)
3. **No fake progress.** No indeterminate spinner for a minutes-long run, no percent bars that aren't measuring anything, no "Thinking…" with animated dots as the *only* signal. Show real structure (skeleton checklist) and real events (clause N done).
4. **No confidence theater.** Never a "94% confident" score, star rating, or traffic-light risk meter on legal findings. The app's own trichotomy — found (cited) / potentially missing / not confirmed — is the honest instrument; anything numeric implies analysis the app forswears.
5. **No three-feature-card rows, no icon-topped marketing cards, no colored 3-4px left-border-as-decoration.** (The clause rows' left border is *semantic* — status-colored, `app.css:178-181` — which is legitimate; never add left-borders that don't encode state.)
6. **No chat-bubble-ification of work product.** The review checklist, the grid, and matter overview are documents/ledgers, not conversations. Resist any future "assistant avatar comments on your contract" pattern.
7. **No dead chrome.** Billing and Referrals are honest today (`app.js:2671-2679` explicitly bans fake Upgrade buttons — good), but pinned nav items with no function are borderline; if they stay, they must never gain placeholder content.
8. **No "AI magic" language.** No sparkle icons (✨ is the single most recognizable AI-slop glyph), no "Ask AI anything!", no "powered by AI" badges. The brand voice is the brief: quiet, factual, source-first.

---

## (e) The 5 highest-impact design debts (file:line, verified)

**1. Contract Review has no progress design for a multi-minute run — the app's worst moment is its most important feature.**
`app.js:2417-2418`: the entire feedback for a synchronous minutes-long `POST /clauses/review` (`routes_clauses.py:35`) is one static muted line ("…this can take a moment."). No skeleton, no per-clause progress, no cancel, and `clause-run` is never disabled (`app.js:2412-2436`) so a double-click silently starts a second full Ollama run. No save/export of the finished review (grid has CSV, `app.js:2505`; clauses have nothing). **Fix:** stream the review per-clause over SSE exactly like `runGrid` (`app.js:2557-2593`), render the taxonomy as skeleton rows immediately (taxonomy endpoint already exists, `routes_clauses.py:28`), swap Run→Cancel during the run, persist the finished review per matter, add export. Highest ROI change in the app.

**2. Watched folders uses a developer affordance (typed absolute path) where the OS provides the attorney affordance (folder dialog).**
`app.js:2124` free-text `folder-path` input; `app.js:2157` conflated validation message ("Choose a matter and enter a folder path") that misfires when only one field is empty — the exact confusion the owner reported. **Fix:** native folder picker via the pywebview JS bridge, folder rendered as a live status object ("Watching · last checked Xs ago · N files added"), entry point added on the matter detail page. Delete the text field from the primary path.

**3. Document Hub is four jobs in one scroll, and "Find in documents" — a primary attorney task — is buried at the bottom of a filing page.**
`buildHub` `app.js:410-457` stacks Upload, Unfiled, Matters, and Find in one column; Find lives at `app.js:445`. Hierarchy inside the panels is carried by bare `<b>` tags (`app.js:435, 439, 445`) rather than a heading component. **Fix:** Find gets its own destination (nav item or top of matter detail) + a cross-link from chat citations; Hub keeps the three filing jobs with real `h2`-level panel titles.

**4. Inline styles are eroding the design system.**
Dozens of `style='…'` attributes in JS-built markup (`app.js:417-455`, `app.js:2114-2148`, error divs repeated as `style='color:var(--err);font-size:13px'` at `app.js:432, 443, 454, 2126, 2628, 2640`, and many more). Every hand-set 13px/13.5px and gap is a future drift point; `app.css` is a genuinely coherent 360-line system being bypassed. **Fix:** promote the repeated idioms to classes (`.panel-title`, `.field-err`, `.form-row`) and sweep — mechanical, low-risk, protects the Ledger long-term.

**5. Off-palette and duplicated status colors — the one place the Ledger visibly breaks.**
`app.js:470`: OS-file drag-over paints the dropzone a *cool blue* `#eef3ff` — the only cold hue in a warm-paper UI, and inconsistent with the matter-card drop target which correctly uses `--accent-soft` (`app.css:258-259`). Meanwhile the ok-tint pair `#e6f0e2/#b6d7bf` is hand-copied at `app.css:46, 92, 172, 271, 291, 331` and warn/err tints similarly (`app.css:93, 95, 96, 173, 187, 251`). **Fix:** one drag-affordance (accent-soft everywhere) and status-tint tokens (`--ok-bg`, `--warn-bg`, `--err-bg`) in `:root`.

---

## Sources

- [NN/g — Skeleton screens vs progress bars vs spinners](https://www.nngroup.com/videos/skeleton-screens-vs-progress-bars-vs-spinners/)
- [Eleken — Progress indicator UX types and best practices](https://www.eleken.co/blog-posts/progress-indicator-ux)
- [Userpilot — Progress bar UI/UX in SaaS](https://userpilot.com/blog/progress-bar-ui-ux-saas/)
- [AWS Agentic AI Lens — streaming responses and time-to-first-token](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentperf02-bp04.html)
- [AG-UI protocol — agent run lifecycle events](https://docs.ag-ui.com/concepts/events)
- [DEVONthink — indexed folders as the watched-folder reference](https://www.devontechnologies.com/apps/devonthink), [community thread](https://discourse.devontechnologies.com/t/indexed-folders/49218)
- [Spellbook (in-Word contract review)](https://spellbook.com/), [Spellbook vs CoCounsel head-to-head](https://www.aivortex.io/legal/compare/spellbook-vs-cocounsel-contract-review/), [GC AI — legal AI tools review](https://gc.ai/blog/legal-ai-tools)
- [925 Studios — AI slop design tells](https://www.925studios.co/blog/ai-slop-design-tells), [Impeccable — Slop](https://impeccable.style/slop/), [SmoothUI — AI design slop](https://smoothui.dev/blog/ai-design-slop), [Why AI keeps building the same purple gradient website](https://prg.sh/ramblings/Why-Your-AI-Keeps-Building-the-Same-Purple-Gradient-Website)
