# Connectors reality gap — adversarial engineering audit

Date: 2026-07-10. Repo: `/Users/janderswag/legal-document-chat` (main, not a git repo — no commit
possible/attempted, no product code modified). Live evidence gathered by launching the installed
`/Applications/docuchat.app` (v0.3.2, `Info.plist:CFBundleShortVersionString=0.3.2`) and curling its
loopback API read-only, then quitting it again. No writes, no keys posted.

## Verdict up front

**The owner is right, RUN_STATE.md is wrong about what shipped.** The 28 connector adapters are
real, correctly written, and pass in the dev/test-suite — but a one-line omission in the PyInstaller
build spec means **zero of them are bundled into the packaged `.app`**. The server API that backs
"28 connectors went LIVE in v0.3.0" returns an **empty list** in the actual installed app. This is
not a UI/CSS bug and not a click-handler bug — the click handlers are correctly wired and correctly
choose not to render a button when the backend has nothing to offer.

## 1. Why unclickable — root cause, file:line

**Claim vs. reality (live curl against the running v0.3.2 app):**

```
$ curl -s http://127.0.0.1:8000/connections/services
{"services":[]}
```

Compare to the same `connectors.registry()` call run in the dev venv against the identical source
tree:

```
$ cd pipeline && python3 -c "import connectors; print(len(connectors.registry()))"
28
```

Same code, two different answers. That is the entire bug.

**Mechanism:**

- `pipeline/connectors/__init__.py:63-77` (`registry()`) discovers adapters *dynamically* at
  runtime with `pkgutil.iter_modules(__path__)` + `importlib.import_module(f"{__name__}.{m.name}")`
  — there is no static `import connectors.gmail`, `import connectors.zoom`, etc. anywhere in the
  codebase (confirmed: `grep -rn "pkgutil\|iter_modules" pipeline/*.py` matches only this one file).
- `desktop/build_macos.spec:31-49` builds `hiddenimports` for PyInstaller. It explicitly calls
  `collect_submodules("uvicorn")` (line 46) and explicitly hand-adds `["api", "sample_matter"]`
  (line 49) — i.e. the author already knows PyInstaller's static analysis misses dynamic imports
  and patches around it for those two cases (the file's own header comment says as much, lines
  10-12). **`connectors` is missing from that list.** PyInstaller's `Analysis()` sees the literal
  `import connectors` in `routes_connections.py:16` and bundles `connectors/__init__.py`, but never
  discovers `connectors.gmail`, `connectors.zoom`, …`connectors.zoho` because nothing references
  those module names as literal strings anywhere in reachable code.
- `desktop/build_windows.spec:10-44` has the **identical** omission — this is a cross-platform bug,
  not a macOS-only quirk.
- At runtime in the frozen app, `pkgutil.iter_modules(__path__)` over the frozen package finds
  nothing (the 28 submodules were never packed into the PYZ archive), so `registry()` silently
  returns `{}` — no crash, no error, no log line. `connectors.services()`
  (`pipeline/connectors/__init__.py:87-90`) then returns `[]`, and
  `GET /connections/services` (`pipeline/routes_connections.py:58-61`) returns `{"services": []}`
  with HTTP 200, exactly as observed above.

**Client-side consequence** (`pipeline/static/app.js`):

- `renderConnectorsPane()` (line 1825) fetches `/connections/services` and populates
  `connState.services` (lines 1830-1835); the fetch itself doesn't throw (200 OK), it's just empty.
- `connectorRowHtml(it)` (lines 1722-1747) branches: `if (live && svc)` → render "Connect" button;
  `else if (live)` → render "Unavailable" (no button) with the comment *"adapter registered as live
  in the catalog but missing from the backend registry — never show a Connect button that cannot
  work"* (line 1734-1736); `else` → render "Coming" (no button, line 1737-1739).
- Because `connState.services` is `{}` for every slug, **all 28 catalog rows marked `live: true`
  fall into the "Unavailable" branch, and the other 20 "Coming" rows never had a button in the
  first place.** Net result: **every single row in the Integration catalog is inert.** This is
  precisely the owner's report — "all unclickable," "none of the connectors actually allow you to
  connect to anything" — and it is accurate for the shipped app, even though the UI code
  defensively did the *right* thing (refusing to show a button that can't work) rather than the
  wrong thing (a dead button).

**Who's wrong:** Nobody lied. The D-81 build (adapters, `routes_connections.py`, `connsync.py`,
tests) is genuinely correct and does pass `pipeline/tests/test_connectors.py`. But that suite runs
`TestClient(api.app)` (`pipeline/tests/test_connectors.py:28`) against the **source tree directly**
— there is no test, smoke check, or CI step anywhere that exercises the actual frozen `.app`. This
is the same class of blind spot RUN_STATE.md itself has flagged before (the WKWebView upload bug,
the keychain incident) — green tests, broken packaged app — but this time nobody caught it before
calling it "LIVE" and shipping three releases (v0.3.0, v0.3.1, v0.3.2) on top of it.

## 2. Desktop API feasibility — how does a local app use these APIs?

Three real patterns exist/are needed, and the codebase already picked the right one for what's
built:

- **API-key / access-token SaaS (Notion, Airtable, HubSpot, Fireflies, Fathom, etc. — 26 of the 28
  "live" adapters):** the user generates a personal/API key in the vendor's own settings UI and
  pastes it into docuchat's connect drawer (`connectDrawerHtml`, `app.js:1749-1780`). Fully feasible
  from a loopback desktop app with zero backend — this is just an authenticated HTTP client
  (`pipeline/connectors/__init__.py:98-141`, `httpx`). No vendor app registration needed. This is
  what's actually built for all 26.
- **"Self-serve OAuth" (Zoom, Zoho — the 2 remaining "live" adapters):** these use a vendor
  mechanism where the *user* creates their own OAuth client in the vendor's developer console
  (Zoom "Server-to-Server OAuth" app, Zoho "Self Client") and pastes `client_id`/`client_secret`
  (+ a short-lived grant code for Zoho — `pipeline/connectors/zoho.py:88-105`, exchanged once via
  the `prepare()` hook `pipeline/routes_connections.py:86-93`). No interactive browser consent
  screen, no redirect URI, no docuchat-owned vendor app. This is also fully feasible from a loopback
  desktop app with zero backend, and it's real, working code — it just can't be reached because of
  the packaging bug above.
- **True 3-legged interactive OAuth (Google, Microsoft, Read AI — everything marked "Coming"):**
  `grep -rn "redirect_uri\|authorization_code\|OAuth" pipeline/*.py pipeline/connectors/*.py`
  finds **no loopback redirect handler anywhere** — no local callback HTTP server, no PKCE, no
  `webbrowser.open()`-and-wait pattern. This is **not built**. It would need: (a) a
  docuchat-owned OAuth client registered with each vendor (Google Cloud Console, Azure AD app
  registration, Read AI's own developer program), (b) a local ephemeral HTTP listener on
  127.0.0.1 to catch the redirect (standard "installed app" / public-client + PKCE pattern —
  technically fine for a loopback app, Google and Microsoft both document this exact flow for
  desktop apps), and (c) for Google specifically, sensitive-scope apps face a verification review
  that can gate public availability for weeks unless the app stays in a 100-user "testing" cap.
  This is real, buildable work, but it's a different shape of work than everything shipped so far.

## 3. Ingest flow — Unfiled tray + drag-to-matter

This part is **built correctly** and is not implicated in the bug:

- `pipeline/connsync.py:50-57` (`_ensure_matter`) — every connector import defaults to
  `matter="unfiled"` unless the user picked a specific matter in the connect drawer; `"unfiled"` is
  lazily created via `catalog.create_matter("Unfiled")`, "same convention as the Document Hub tray"
  (comment, line 52).
- `pipeline/connsync.py:60-80` (`_store_item`) — imported bytes go through the **same** managed-copy
  + catalog + ingest-queue path as a manual upload (`routes_kb.KB_DOCS / matter`, DEK-encrypted,
  `ingest_worker.enqueue`).
- `pipeline/routes_kb.py:104-147` (`POST /kb/documents/move`) — re-filing exists and is real: moves
  the managed file, re-keys the DEK for the destination matter, updates the catalog row, appends an
  audit event.
- `pipeline/static/app.js:392-699` — the Unfiled tray UI (`refreshUnfiled()`, line 659) renders
  draggable document rows (`tr[draggable]`, lines 651-658) and matter cards with `dragover`/`drop`
  handlers (lines 693-701) that call the move endpoint, plus a non-drag "Move to" `<select>`
  fallback (line 627) for accessibility/no-drag environments.

**Conclusion:** the owner's expected flow (Unfiled → drag into a matter) is fully implemented today
for manual uploads and watched folders. It is simply unreachable *for connectors specifically*
because no connector import can ever start (bug #1) — there is nothing to drag yet.

## 4. Value ranking — 28 live (claimed) + 20 planned, by solo-attorney value

Full catalog, `pipeline/static/app.js:1627-1687` (`CONNECTOR_CATALOG`), 8 categories, 48 entries,
28 flagged `true` (live) / 20 flagged `false` ("Coming"). Live-flag count independently verified
against the adapter files on disk (`ls pipeline/connectors/*.py` = 28 files, slugs match exactly).

| # | Connector | Category | Catalog status | Notes |
|---|---|---|---|---|
| 1 | **Gmail** | Email & Communications | live (blocked) | Primary correspondence + attachments for a solo practice; IMAP app-password, `pipeline/connectors/gmail.py` |
| 2 | **Clio Manage** | Legal Practice & Case Management | **Coming — not built** | The dominant solo/small-firm practice-management tool; matters+documents+contacts live here natively |
| 3 | **Google Drive** | Cloud File Storage | **Coming — not built** | Most common generic document repository for solo/small firms today |
| 4 | **Zoom** | Meeting Platforms | live (blocked) | Depositions, client calls, cloud-recording transcripts, `pipeline/connectors/zoom.py` |
| 5 | **E-signature (DocuSign/HelloSign/PandaDoc/SignWell)** | — | **Not in the catalog at all** | Zero coverage of any kind, live or planned — a real gap: executed retainers/contracts/settlements are core legal documents |
| 6 | **Dropbox** | Cloud File Storage | Coming — not built | Still very common for law-firm file sharing |
| 7 | **Fireflies.ai / Fathom** | AI Meeting Notetakers | live (blocked) | Call/negotiation transcripts, `pipeline/connectors/fireflies.py`, `fathom.py` |
| 8 | **Microsoft OneDrive/SharePoint** | Cloud File Storage | Coming — not built | Dominant in Office-365-centric firms |
| 9 | **ShareFile** | Cloud File Storage | live (blocked) | Citrix ShareFile is a real legal-industry client-portal tool, adapter already written, `pipeline/connectors/sharefile.py` |
| 10 | **MyCase / Lawmatics** | Legal Practice & Case Management | Coming — not built | Other common solo-attorney PM/intake tools |

Everything else live today (Granola, tl;dv, MeetGeek, Avoma, Grain, Jiminny, Rev AI, Sonix, Trint,
Happy Scribe, Webex, Notion, Confluence, Airtable, Coda, ClickUp, monday.com, Asana, Slack,
Nextcloud, HubSpot, Zoho CRM, Pipedrive) is real, working adapter code, just also blocked by bug #1
— lower-ranked here mainly because they're less likely to be *where a solo attorney's legal
documents actually live* (they're team-collaboration/CRM tools whose file attachments are a
secondary source, not the primary one). Everything else "Coming" (Read AI, Rev, Circleback, MS
Teams, Google Meet, Google Docs, OneNote, MS Word, Dropbox Paper, Outlook, Box, Actionstep, LEAP,
Litify, NetDocuments, Salesforce) ranks below the top 10 for the same reason plus not-yet-built.

## 5. Fix cost — top 5 by value

**#1 shared fix (unlocks #1, #4, #7, #9, and every other already-"live" adapter at once):**
Add `hiddenimports += collect_submodules("connectors")` to `desktop/build_macos.spec` (after line
46) and the equivalent line to `desktop/build_windows.spec`. One-line change per spec file, then a
full rebuild + a packaged-app smoke test that specifically curls `GET /connections/services` and
asserts `len(services) == 28` (a check that has never existed — add it to whatever pre-release
checklist gates a release, since this exact class of bug has bitten this project three times now
per RUN_STATE.md). **Estimate: 0.5–1 day**, almost all of it verification/rebuild/notarize
turnaround rather than code.

- **Gmail (#1):** 0 additional engineering beyond the shared fix. Recommend ~0.5 day of manual
  end-to-end verification with a real Google app password post-fix (security-sensitive path,
  already got one CVE-class fix in v0.3.1 for unverified TLS).
- **Clio Manage (#2):** **Not a paste-a-key connector** — Clio's public API is OAuth-only (no
  personal-access-token option for third-party integrations), and Clio's App Directory has its own
  review/approval process for a published integration. Needs: new adapter module + the interactive
  OAuth loopback-redirect infrastructure described in §2 (not built at all today) + Clio's own
  vendor approval, which is calendar time outside engineering's control. **Estimate: 3–5 engineering
  days once the shared OAuth infra exists, plus an unknown/variable wait for Clio's app review.**
- **Google Drive (#3):** Needs the same OAuth loopback infra (shared cost, build once) + a Google
  Cloud OAuth client registration + Drive adapter. Google's verification review for
  sensitive/restricted scopes (Drive file access qualifies) can take **weeks** for a public app, or
  the app must stay capped at 100 test users indefinitely. **Estimate: 4–6 engineering days** for
  the OAuth infra + adapter, **plus real risk of a multi-week Google review before it can ship to
  anyone but the owner.**
- **Zoom (#4):** 0 additional engineering beyond the shared fix — adapter exists, Server-to-Server
  OAuth pattern needs no interactive consent. **Estimate: ~0.5 day** verification only.
- **E-signature / DocuSign (#5, currently absent):** New adapter from scratch. DocuSign's sandbox
  works immediately for a self-key-paste style connect, but **production API access requires
  DocuSign's own "Go-Live" review** before real client documents can flow through it — another
  vendor-side approval gate. Can reuse the OAuth loopback infra built for Drive. **Estimate: 3–4
  engineering days + DocuSign go-live review lead time** (not engineering-controlled).

**Bottom line:** the fastest, highest-leverage fix is the 0.5–1 day packaging change — it alone
turns "0 of 28 connectors work" into "26 work today, 2 (Zoom, Zoho) need trivial verification."
Everything requiring real interactive OAuth (Clio, Drive, DocuSign, and the rest of "Coming") is
materially more expensive and partly gated by vendor review processes docuchat doesn't control —
that's a multi-week program, not a bugfix.

## Evidence index

- `pipeline/connectors/__init__.py:63-90` — `registry()`/`services()`, dynamic `pkgutil` discovery
- `pipeline/routes_connections.py:58-61` — `GET /connections/services`
- `pipeline/routes_connections.py:75-98` — `POST /connections` (test → seal → store, D-81 contract)
- `pipeline/routes_connectors.py:1-51` — separate, unrelated "watched folders" router (not the
  live-connector catalog; easy to conflate given both live under `/connectors*`)
- `pipeline/static/app.js:1627-1687` — `CONNECTOR_CATALOG` (48 entries, 28 `true`)
- `pipeline/static/app.js:1722-1747` — `connectorRowHtml` live/svc branching
- `pipeline/static/app.js:1825-1903` — `renderConnectorsPane`
- `pipeline/static/app.js:1905-1980` — `wireConnectionEvents` (click handlers — correctly wired)
- `desktop/build_macos.spec:31-49`, `desktop/build_windows.spec:10-44` — missing
  `collect_submodules("connectors")`
- `pipeline/connsync.py:50-80` — Unfiled default + managed-copy ingest path
- `pipeline/routes_kb.py:104-147` — `POST /kb/documents/move`
- `pipeline/static/app.js:392-699` — Unfiled tray, drag/drop, move-to select
- `pipeline/tests/test_connectors.py:28` — `TestClient(api.app)`, source-tree only, no packaged-app
  coverage
- Live curl (this session, v0.3.2, `/Applications/docuchat.app`): `GET /connections/services` →
  `{"services":[]}`; `GET /connections` → `{"connections":[]}`; `GET /connectors/folders` →
  `{"folders":[],"poll_seconds":15}`
- Dev-venv control: `python3 -c "import connectors; print(len(connectors.registry()))"` → `28`
