# Adversarial audit: Watched Folders + "Find in documents"
_Council 2026-07-11 — engineering/UX auditor seat. Read-only audit; every claim cites file:line._

---

## Part 1 — Watched Folders (Settings → Connectors)

### 1a. The owner's confusion, reproduced from the code

**Why it says "Choose a matter and enter a folder path" with a matter selected.**
The add handler is one conflated guard:

- `pipeline/static/app.js:2157` — `if (!matter || !path) { err.textContent = "Choose a matter and enter a folder path."; return; }`

The matter picker (`#folder-matter`, app.js:2123) is a `.matter-picker`, and `fillMatterPickers()` pre-selects the active matter (app.js:87 `if (state.matter) sel.value = state.matter`). So in the owner's session the matter **was** selected. What was empty was the free-text **path** input (app.js:2124) — the owner never typed one because he expected a folder dialog. The error message then wrongly implies the matter also wasn't chosen. The message is a two-condition guard with a one-size-fits-none string. This is the entire confusion: **the UI asks the user to hand-type an absolute POSIX path** (`placeholder='/Users/you/Scans or a synced folder'`, app.js:2124), which is a developer interaction, not an attorney interaction.

Secondary race: `renderConnectorsPane()` injects the empty `<select>` then calls `fillMatterPickers().catch(function(){})` async (app.js:2150), so for a beat the picker really is empty — a fast click hits the same message legitimately.

**What EXACTLY happens on click with empty/invalid path — is there feedback?**
There is feedback, but it is nearly invisible:

- Empty path → the 13px red line `#folder-err` (app.js:2126) gets the conflated message above. No dialog, no focus move, no highlight on the offending field. On a large settings page this reads as "nothing happened."
- Non-empty but invalid path → `POST /connectors/folders` (app.js:2158-2162) → server-side `watchers.validate_folder` raises with reasonable strings — "folder path must be absolute" (watchers.py:48), "not a folder: …" (watchers.py:51), "cannot watch docuchat's own document store" (watchers.py:58) — surfaced via `err.textContent = e.message` (app.js:2164). Correct, but again a 13px line.
- Success → silent re-render; the new row appears in the table (app.js:2108-2113). No confirmation, no "it will be checked in 15s" moment.

So the button never "does nothing" in code — but the *perceived* result of the most natural click (button with empty path) is a small red sentence that blames the user for two things when one was already done. Owner's report is fully explained.

### 1b. Native folder picker — feasible today?

**Yes, with one addition to the launcher; nothing exists yet.** Audit of the bridge surface:

- `desktop/launcher.py:538-541` — `webview.create_window("docuchat", html=SPLASH_HTML, ...)` is created with **no `js_api=` and no `window.expose()` anywhere** (grep over desktop/ finds zero `js_api`/`expose`/`create_file_dialog` hits). The only launcher→page channel today is one-way `evaluate_js` for splash text (launcher.py:493-499).
- The Document Hub's existing "upload a folder" affordance is a `webkitdirectory` `<input>` (`#hub-folder-input`, app.js:461-467) — it uploads file *contents*; WKWebView never reveals the on-disk path, so it cannot be reused for watching.

The fix is the textbook pywebview pattern: expose one function (e.g. `window.expose(pick_folder)` or a tiny `js_api` object) that calls `window.create_file_dialog(webview.FOLDER_DIALOG)` and returns the chosen path string; the page then does exactly the POST it does today (app.js:2158-2162). pywebview injects `window.pywebview.api.*` into every `load_url` page when an API is exposed, and `create_file_dialog` marshals to the main thread itself. Estimated size: ~10 lines in launcher.py + ~15 in app.js. **Required fallback:** in dev (`make run` in a browser, and the DOCUCHAT_SMOKE headless path, launcher.py:517-535, which never creates a window) `window.pywebview` is absent — keep the text input as the fallback branch, shown only when the bridge is missing. One real risk to test in the packaged app per the WKWebView lesson: the dialog must be requested after `pywebviewready`, and the smoke gate never exercises it — add a bridge-presence assert to `desktop/smoke_packaged.sh` or accept it's manually gated.

### 1c. How the watcher actually works (and its failure surfaces)

- **One daemon thread**, started idempotently (watchers.py:133-141), polls every **15s** (watchers.py:29); connector sync piggybacks on the same tick (watchers.py:124-127).
- **Pickup rules** (watchers.py:101-113): file (not dir), suffix in the upload allowlist (watchers.py:36-38 → `routes_kb._ALLOWED`), name not dot-prefixed, **filename not already present in the matter** (watchers.py:95-96, 104), and mtime ≥2s old so half-written files wait a tick (watchers.py:30, 107).
- **Ingestion = the manual-upload path**: bytes copied into the managed KB tree DEK-encrypted, catalog row `status="queued"`, serialized ingest worker enqueued (watchers.py:62-81). Content-differing name collisions get `-1`, `-2` suffixes (watchers.py:71-74). Originals never touched (module docstring, watchers.py:16-17). This is the right architecture — one ingest path, no fork.
- **Failure surfaces are almost all silent:**
  - The loop swallows *everything*: `except Exception: pass` (watchers.py:121-122). A crashing pass leaves zero trace anywhere, including logs.
  - Missing/renamed folder → skipped silently (watchers.py:91-92); the UI does show `missing` on the row (app.js:2110-2111) — the *only* live status surface.
  - Disposed matter → row inert forever, still listed as "watching" (watchers.py:93-94 vs routes_connectors.py:32 which only checks the dir).
  - Unsupported suffix, empty file (watchers.py:66-67), unreadable file (OSError, watchers.py:110-111) → silently skipped, forever.
  - **No recursion**: `folder.iterdir()` (watchers.py:98) — a scanner that writes date-subfolders (`Scans/2026-07-11/…`) will never be picked up, with no hint why.
  - **Filename-only dedupe at scan level** (watchers.py:104): replace `contract.pdf` in the folder with a corrected version → never re-ingested, silently.
  - No "last checked" timestamp, no "N files added" count, nothing in the UI ever confirms the watcher is alive. Test coverage exists for happy paths in `pipeline/tests/test_connectors.py`, but none of the silent-skip cases assert a user-visible surface — because there isn't one.

### 1d. Verdict: necessary? And the smallest redesign

**Keep it — it is load-bearing, not redundant.** The catalog's own copy admits cloud drives are "Coming" and points users here: "for cloud drives, a synced folder above covers the gap today" (app.js:2147-2148). Watched folders are the **only** path for (a) Dropbox/Drive/OneDrive synced folders, (b) scanner scan-to-folder — both core solo-attorney workflows — with zero network code (watchers.py:1-18). Drag-drop is one-shot; this is the standing pipe. Killing it would orphan the cloud-drive story.

**Smallest redesign that makes it self-explanatory (in priority order):**
1. **Native folder picker via the pywebview bridge** (1b). The text input becomes the no-bridge fallback only. This alone dissolves the owner's confusion.
2. **Split the guard, name the field** (app.js:2157): empty path → "Choose the folder to watch" + focus/outline the picker button; no matter → "Choose a matter". Never blame both.
3. **Give the row a heartbeat**: extend `GET /connectors/folders` (routes_connectors.py:28-33) with `last_scan` and `files_added` (two columns on `watch_folders`, catalog.py:132, written by `scan_once`) and render "checked 12s ago · 4 files added" instead of the bare "watching". This converts an invisible daemon into a legible one and surfaces the disposed-matter dead row for free.
4. Small honesty fixes while there: recurse one level or state "subfolders are not watched" in the panel copy; log (not `pass`) in the loop's except (watchers.py:122).

Not recommended: watchdog/fsevents, per-file status feeds, or folder-level ingest options — poll-15s is fine at this scale and everything else is speculative.

---

## Part 2 — "Find in documents" (Document Hub panel)

### 2a. What it actually does vs chat and `/find`

Three things share the word "find"; they are mechanically different:

| Surface | Mechanism | Output |
|---|---|---|
| **Find in documents** panel (app.js:445-455 → `runSearch` app.js:1715-1754) | `GET /search` (routes_search.py:74-130). `mentions` mode = exhaustive normalized-substring scan over every chunk in the matter with a TRUE total (routes_search.py:112-130); `fts` mode = BM25 via LanceDB FTS with staleness-guarded index rebuild (routes_search.py:40-44, 96-110). **Zero LLM, zero embedding query.** | Every hit, filename + page + snippet, each linking into the highlight viewer (app.js:1731-1735); paginated with honest truncation labels (app.js:1739-1744). |
| **Chat answer path** | Top-k semantic retrieval → generation → mechanically verified citations. | An *answer*, top-k only — structurally cannot be exhaustive. |
| **`/find` slash command** (app.js:1614-1620) | Pure composer template: rewrites the input to "Where do this matter's documents discuss X?" and the attorney presses Ask → the **chat** path. | Same as chat. |

So the panel and `/find` are **not** the same retrieval, not the same guarantees, not even the same subsystem. The panel is the only surface in the product that can honestly say "this term appears exactly 37 times, here is every one" — which is a genuine litigation workflow (privilege-style term sweeps, every mention of a name/amount/defined term) that the QA path *structurally cannot serve* (routes_search.py:6-10 says exactly this). The panel copy already tries to say so (app.js:446-447).

One real wiring subtlety verified: the panel's own matter `<select>` (`#search-matter`, app.js:449) is not read by `runSearch` — it goes through global `state.matter` (app.js:1721, 1726) — but the select's change handler calls `setActiveMatter` (app.js:492-495) which syncs all pickers (app.js:66-68), so they can't drift. Correct, just indirect. The `/search` route is solid: matter validated against the store allowlist (routes_search.py:92-94), loopback read-only, tests in `pipeline/tests/test_search_routes.py` (97 lines).

### 2b. Is it redundant?

**No — but it is illegible, and the naming actively lies.** The problems:

1. **Name collision**: the slash command `/find` (app.js:1521) does the *opposite* of the "Find in documents" panel — it routes to the generative top-k path. An attorney who learns one will wrongly generalize to the other.
2. **Location**: an exhaustive-search tool lives as the *fourth panel* of the Document Hub home (app.js:445), below upload, Unfiled, and Matters — discoverable only by scrolling a management screen. Search is a task, not a filing-cabinet feature.
3. **Mode dropdown**: "Every mention" vs "Best match" (app.js:451-452) is engineer vocabulary for substring-vs-BM25; nothing explains when to use which, and "Best match" quietly loses the total count (routes_search.py:107-110), which looks like a bug to a user.

### 2c. Options and recommendation

- **Kill it** — wrong. It's the only exhaustive, zero-hallucination surface; core-principle aligned (retrieval-only, every result a real chunk). Killing it makes "find every mention of X" impossible in the product.
- **Merge into chat** — wrong. Folding it behind the composer would either bolt a non-LLM mode onto the frozen answer engine (gate risk for a UX shuffle) or mislabel exhaustive results as "answers."
- **Make it legible** — right, and cheap:
  1. **Rename the panel** to **"Every mention"** (its own words, app.js:452) or "Exact search", and rename the slash command from `/find` to `/ask-where` — or better, repoint `/find` at this panel (slash commands already navigate to views, app.js:1596-1612; precedent exists). One name must mean one mechanism.
  2. **Promote it**: hoist to the top of the Hub or give it the nav slot the old Search view had before it was folded in (app.js:1756-1757 records that fold as an owner decision — worth revisiting now that the owner himself can't place it).
  3. **Replace the mode dropdown** with two labeled radio-style choices: "Every mention — exact text, counted" / "Best match — ranked, for when you don't know the exact wording". Default stays `mentions`.
  4. **Cross-link from chat**: when a cited answer comes back, a one-line "See every mention of '<term>' →" affordance would teach the relationship between the two paths instead of leaving it implicit.

**Bottom line:** Watched Folders and Find-in-documents are both architecturally sound and both worth keeping; both fail the same way — correct machinery behind an interface that never explains itself. The fixes are interface-sized, not engine-sized, and none touch the frozen answer path.
