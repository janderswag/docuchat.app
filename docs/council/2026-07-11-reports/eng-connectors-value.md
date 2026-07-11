# Engineering audit: connector INGESTION VALUE (not connectivity)

Auditor: adversarial engineering seat, 2026-07-11 council.
Scope: what a pulled remote item BECOMES, whether it delivers a cited answer, and where the value leaks. Connectivity itself was proven in v0.4.1 and is out of scope.
Every claim cites file:line in this repo as of 2026-07-11.

---

## 1. Direct answer to the owner's question

**When a meeting transcript / email / Slack file / CRM note is pulled, what does it become?**

A real file on disk, in a real matter, on exactly the manual-upload path:

1. `connsync.run_import` asks the adapter for a listing, filters out already-seen source ids, and fetches each fresh item as `(filename, bytes, provenance)` (`pipeline/connsync.py:98-115`).
2. The bytes are written as a DEK-encrypted managed copy under the target matter, a catalog row is created with `source_json` provenance, and the doc is enqueued on the SAME serialized ingest worker as an upload (`pipeline/connsync.py:60-80`).
3. Target matter defaults to **Unfiled** (created lazily, `pipeline/connsync.py:50-57`); the user can instead bind a connection to a specific matter at connect time (`pipeline/routes_connections.py:26-27, 83-98`). Unfiled items appear in the Document Hub tray and are dragged onto a matter (`pipeline/static/app.js:435-438, 685`), which re-files and re-ingests (`pipeline/catalog.py:707-720`).
4. Ingest = extract -> chunk -> embed -> matter-digest facts, identical to an upload (`pipeline/ingest_worker.py:89-119`). So yes: an imported transcript gets span-verified digest facts and cited answers exactly like a dragged-in PDF.

**Formats produced per family:**

| Source | File written | Extracted as |
|---|---|---|
| Gmail email | raw RFC822 `.eml` (`connectors/gmail.py:274`) | headers + best text body, single page (`extractors.py:67-107`) |
| Fireflies transcript | `.vtt` with `<v Speaker>` voice tags, `.txt` or summary `.md` fallback (`connectors/fireflies.py:144-163`) | `[HH:MM:SS] Speaker: text` lines (`extractors.py:135-159`) |
| Zoom recording | vendor WebVTT `.vtt` (`connectors/zoom.py:139-152`) | same VTT path |
| Slack | the shared FILE's own bytes (pdf/docx/...) (`connectors/slack.py:161-180`) | per its own type |
| HubSpot note | rendered `.md`; attached files as their own bytes (`connectors/hubspot.py:117-150`) | text |

**Sync:** manual Import button (`routes_connections.py:108-112`) plus optional polling: the watcher tick calls `connsync.sync_due()` and re-imports sync-enabled connections at most every 30 minutes (`connsync.py:25, 151-171`; `watchers.py:125-127`).

**Dedupe:** by `(connection_id, source_id)` ledger (`connsync.py:99-100`; `catalog.py:394-411`), then filename+content compare within the matter (`connsync.py:69-72`). An item imports once per connection.

**Metadata:** rich provenance is captured per item: email From/To/Date/Message-ID (`gmail.py:264-272`), transcript speakers/date/host/url (`fireflies.py:133-141`), Slack channels/permalink (`slack.py:172-179`), and stored as `source_json` (`connsync.py:112-117, 77`).

**Speaker turns are NOT lost.** `extractors.py:155` converts `<v Speaker>` to `Speaker: ` and keeps a `[HH:MM:SS]` anchor per cue. This is the single best-executed detail in the whole path: "who said what when" is searchable and citable.

---

## 2. Findings (ranked; each = a value leak with file:line)

### F1 (Critical, correctness) — Gmail can never import past the oldest 500 messages
`gmail.py:203` caps `UID SEARCH ALL` results to the FIRST 500 UIDs, i.e. the oldest 500, every pass. The module docstring promises "rerun the import to continue" (`gmail.py:16-17`), but a rerun re-lists the same oldest 500, all already in the seen ledger, so `fresh` is empty (`connsync.py:100`) and the import reports success with 0 imported. Consequences for a label with >500 messages: (a) messages 501+ are permanently unreachable; (b) NEW mail (higher UIDs) is never picked up, so the sync toggle silently does nothing on exactly the mailboxes that matter. Fix shape: exclude seen UIDs before capping, or track the max imported UID and search `UID <max+1>:*`.

### F2 (Critical, value) — Email attachments are stored but their CONTENT is unsearchable
The Gmail card promises "attachments included" (`gmail.py:41-42` blurb; also the catalog card). The raw `.eml` does contain the attachment bytes, but the extractor deliberately lists attachment FILENAMES only (`extractors.py:70-72, 95-100`). For an attorney, the email is often just the envelope; the contract redline, the signed PDF, the exhibit IS the attachment. Today "what does the attached amendment say" returns nothing, while the UI copy says attachments came along. Either extract attachments as child documents at ingest (they already pass through the same `_ALLOWED` gate, `routes_kb.py:29`) or change the blurb to stop over-promising. This is the largest single gap between promised and delivered value in the connector surface.

### F3 (High, value) — Provenance is captured then dropped on the floor
`source_json` is written at import (`connsync.py:77`; `catalog.py:502-519`) and returned by `SELECT *` (`catalog.py:694-704`), but NOTHING reads it: zero references in `static/app.js`, retrieval, digest, or citations. So the Document Hub shows a Fireflies transcript as just another row; the user cannot see "from Fireflies, 2026-06-12, speakers: A, B, link to source", cannot filter Unfiled by connector, and answers cannot say "per the March 3 call". The system did the hard part (collecting participants, dates, message ids, channels) and skips the cheap part (showing it). Minimum viable fix: a source badge + date + participants line on Unfiled/matter rows, sourced from `source_json`. That alone would make triaging a 50-item Unfiled dump feasible.

### F4 (High, efficiency/cost) — "Sync" is a full re-list every 30 minutes; `since` exists but is never passed
Every adapter accepts `since` (`connectors/__init__.py:25`; `zoom.py:87`; `hubspot.py:67`), but `connsync.run_import` calls `adapter.list_items(creds)` bare (`connsync.py:98`). Each 30-minute pass therefore re-walks everything: Zoom re-walks 24 months in 30-day windows (~24+ calls, `zoom.py:97-135`); HubSpot re-pages the entire portal's notes AND file manager (`hubspot.py:70-106`). Worst case is Fireflies Free, advertised as "works on Free (50 API requests/day)" (`fireflies.py:35-37`): sync alone burns ~48 list calls/day, so the quota is exhausted by polling before a single new transcript is fetched, and the connection sits in `last_error`. Wire `last_sync` into `since` (it is already stored, `catalog.py:366`).

### F5 (Medium, dedupe) — Disconnect + reconnect duplicates the whole corpus
`remove_connection` deletes the seen-id ledger while keeping documents (`catalog.py:382-390`, intentional per D-80). Reconnecting the same account then re-imports every item; `_store_item`'s content check exits its rename loop on an equal body and still inserts a SECOND catalog row for the same path (`connsync.py:69-77`), which then re-ingests. Result: duplicate rows in the Hub and duplicate chunks in the store after any key rotation (and Gmail app passwords are revoked on every Google password change, `gmail.py:61-65`, so reconnects are the NORMAL lifecycle, not an edge case). Fix: dedupe on checksum at `add_document`, or keep the ledger keyed by (service, account) rather than connection id.

### F6 (Medium, value) — CRM imports are firm-wide dumps of context-free notes
HubSpot lists ALL notes and ALL files in the portal with no client/deal filter (`hubspot.py:67-106`), and a note renders with "Linked records: contacts 1234, deals 5678" as bare numeric IDs, never resolved to names (`hubspot.py:134-138`). An attorney gets their whole firm's CRM exhaust in Unfiled, each note unattributable to a client without opening HubSpot. For a matter-centric product this is negative value: it floods the triage tray. CRM needs a filter (by company/deal) at connect time and ID->name resolution, or it should be honestly labeled "everything, unfiltered".

### F7 (Medium, honesty) — Slack imports FILES only; a "Slack thread" is not a thing docuchat can ingest
`list_items` is `files.list` filtered to document extensions (`slack.py:127-158`). Messages and threads are never fetched, even though the setup steps demand the `channels:history` scope (`slack.py:44`) that the adapter never uses. The owner's mental model ("does the thread get pulled in?") is wrong today and nothing in the UI corrects it. Either build channel-export-to-document (the history scope is already requested) or drop the scope and set the blurb expectation to "files shared in Slack".

### F8 (Low) — Unsupported extensions are marked seen forever
A skipped item is recorded in the ledger with a null doc id (`connsync.py:106-110`), so if a format becomes supported later (e.g. .xlsx), previously listed items never re-import without a disconnect (which triggers F5).

### F9 (Low, citation granularity) — Every transcript/email is page 1
`.eml`/`.vtt`/`.md` extract as a single page (`extractors.py:103, 110-117, 159`). Citations on a 90-minute transcript all read "page 1"; the real anchor is the in-text `[HH:MM:SS]` stamp, which survives in the span. Acceptable, but the citation UI could surface the timestamp instead of a meaningless page number.

### F10 (Low, UX) — Sync can only be chosen at connect time
`sync` is a field of `NewConnection` (`routes_connections.py:27`); the route surface (services/list/create/test/import/status/remove) has no update verb, so turning sync on/off later means disconnect + reconnect, which triggers F5.

---

## 3. Value ranking by family: delivered TODAY vs promised

Rank by real attorney value delivered today (path actually producing cited answers):

1. **AI notetakers (Fireflies + 8 others) — HIGH delivered.** Best family end to end: full transcript, speakers and timestamps preserved (`fireflies.py:144-158`; `extractors.py:135-159`), becomes digest facts and citable spans. Leaks: F3 (provenance invisible), F4 (Free-tier quota burned by polling), F9. This is the family to demo.
2. **Meeting platforms (Zoom, Webex) — MEDIUM-HIGH delivered.** Same VTT path; real preconditions (paid plan, "Audio transcript" setting, `zoom.py:52-53, 13-14`) are honestly disclosed. Leak: F4 (24-month re-walk per sync).
3. **Email (Gmail) — MEDIUM delivered, HIGH promised.** The design (label = matter, raw `.eml`, headers searchable, read-only IMAP) is exactly right for attorneys, and it is the family attorneys need most. But F1 (500-message dead end that silently breaks sync on real mailboxes) and F2 (attachment content invisible despite "attachments included") cut the delivered value roughly in half. Fix F1+F2 and email becomes the #1 family.
4. **Transcription services (Rev.ai, Sonix, Trint, HappyScribe) — MEDIUM delivered, niche.** Mechanically same as notetakers; relevant to attorneys who send depositions/hearings out for transcription.
5. **Notes/docs + work management (Notion, Confluence, Coda, Asana, ClickUp, Monday, Airtable) — LOW-MEDIUM.** Text pages become searchable, fine; but weak matter affinity means Unfiled flooding, and F3 makes triage blind.
6. **Team chat (Slack) — LOW delivered.** Files-only (F7); the thing users imagine (threads) does not exist.
7. **CRM (HubSpot, Pipedrive, Zoho) — LOW delivered, arguably negative** until F6 (portal-wide dumps, numeric-ID notes) is fixed.
8. **Cloud storage (Nextcloud, ShareFile) — LOW delivered by vendor mismatch.** The mechanics are fine, but the storage attorneys actually use (Google Drive, OneDrive, Dropbox, Clio, NetDocuments) is all "Coming" (`static/app.js:1944-1959`; OAuth registrations pending per RUN_STATE). The honest bridge today is a watched folder pointed at a Drive/Dropbox sync folder, and the UI even says so (`static/app.js:2120-2121`), but the owner reports watched folders are unusable (another seat's lane). Fixing watched folders IS the storage-connector story for this cycle.

## 4. What to build (smallest set, biggest value recovery)

1. Fix F1 (Gmail cap) and F2 (attachment extraction as child docs). Email jumps to #1.
2. Surface `source_json` in the Hub (badge + date + participants) and in Unfiled triage (F3). Cheap, uses data already stored.
3. Pass `last_sync` as `since` in `connsync.run_import` (F4). One line plus adapter trust; saves Fireflies Free from self-DoS.
4. Checksum dedupe at `add_document` (F5) so reconnects are safe.
5. Do NOT invest in CRM/chat breadth this cycle; fix depth in email + notetakers + watched folders instead. 28 shallow connectors already outnumber the attorney's actual sources.
