# Overnight sprint brief — 2026-07-10 → 07-11: MAKE IT REAL (v0.4.1)

_Read RUN_STATE.md and docs/council/2026-07-10-council-make-it-real.md first. This brief is
the owner-approved scope. Owner is asleep: work autonomously, small gated steps, never
violate the hard rules (CLAUDE.md). The four council reports in
docs/council/2026-07-10-reports/ carry file:line evidence for every claim below._

## Mission

Everything the app claims, the shipped app does. Documents flow IN by themselves
(connectors), verified deadlines flow OUT (calendar), and the release script refuses to ship
a bundle that can't prove it.

## Definition of done (owner's morning test, no terminal)

Update to v0.4.1 in-app → Settings → Connectors lists real services → paste one API key →
documents land in Unfiled with provenance → drag one onto a matter → matter overview shows
its facts → confirm a deadline → Add to calendar puts it in Calendar.app with the source
quote in the notes.

## Work items, priority order

1. **Connectors packaging fix.** Root cause (connectors-audit.md): `connectors/__init__.py`
   discovers adapters via `pkgutil.iter_modules`; neither PyInstaller spec collects them →
   shipped registry is empty, UI hides Connect buttons. Fix both specs
   (`collect_submodules("connectors")` + any data files). Prove in the BUILT app:
   `/connections/services` lists 26+.
2. **Packaged-app smoke gate** (the institutional fix — third source-tested/bundle-broken
   incident). Extend the release script: after build, launch the .app binary against a
   scratch data dir (env-overridable paths exist — see apppaths.py) and assert: server
   healthy, `/connections/services` non-empty, a test upload ingests, `/matters/{slug}/overview`
   renders, bundle version == appversion.APP_VERSION. Non-zero exit = no release. Wire it
   into build_macos.sh (skippable only with an explicit SKIP_SMOKE=1).
3. **End-to-end connector verification** (top of value ranking, connectors-audit.md): pick
   the 2–3 highest-value adapters that need only an API key (per the audit: Gmail app
   password, Zoom, plus one file/notes service) and verify against REAL free/trial accounts
   if credentials exist in the keychain/test fixtures — otherwise verify the full local flow
   with the adapter's mocked transport AND document exactly what the owner must paste to go
   live. Confirm import → Unfiled → drag-to-matter works in the packaged app. Honest catalog
   pass: anything that can't actually connect gets demoted to Planned (product rule: never
   list a connector a user discovers they cannot connect).
4. **Deadline → calendar (.ics).** "Add to calendar" on every confirmed deadline row in the
   matter overview: serve a well-formed .ics (SUMMARY = deadline label + matter, DTSTART =
   attorney-confirmed date, DESCRIPTION = verbatim source quote + filename p.N, no alarms
   presumption — keep it simple). Plus the ethics disclaimer line on the Deadlines panel:
   short, persistent, LawToolBox-class ("Extracted from your documents — verify against the
   source. Not a complete docket."). UI matches the cream/bronze system; esc() everything.
5. **Copy the cited answer.** A copy button on chat answers: answer text + numbered
   citations (filename p.N + quoted span) to the clipboard as clean plain text.
6. **Trust polish (three small fixes, gaps-audit.md):** (a) first-run race — suggested
   sample-matter question must not 400/refuse while ingest is in flight (disable with a
   "preparing your sample matter…" state until ready); (b) Time Machine exclusion failure
   surfaces in Settings (one honest line, not silent); (c) digest empty state distinguishes
   "no extractable facts" from "couldn't read this document".
7. **Shop window.** README.md rewrite: current feature set (matters, transcripts w/
   page:line, digest overview + attorney-confirmed deadlines, connectors, one-click
   updates), the *Heppner*/local-first positioning WORDED PER THE ETHICS SEAT ("removes the
   vendor from the privilege analysis" — never "privilege can't be waived"; every accuracy
   number must trace to our eval artifacts), fresh `docs/demo.png` screenshot of the cream
   UI showing a matter overview with deadlines (packaged app or dev server + real synthetic
   matter; the old PNG is the pre-digest design). No em-dashes in user-facing copy. No
   "built by AI" framing.
8. **Ship v0.4.1:** bump appversion (spec now derives from it), full test suite
   (test_digest_* + connectors + new smoke), 63/63 golden ONLY if anything touched
   answering/retrieval/verifier (it must not), packaged smoke gate green, sign + notarize +
   staple + Gatekeeper, publish as Latest, verify releases/latest redirect, update
   RUN_STATE.md top entry with honest results incl. anything that failed or was cut.

## Out of scope tonight (queued, do not start)

OAuth connector flows (Clio/Google/Microsoft/Read AI — blocked on owner registrations,
docs/2026-07-10-connector-registrations.md), Windows build, retention-schedule policy layer,
fact router, M-1 query rewriting, cross-matter "due this week", DocuSign adapter (missing
from catalog — note it in the plan doc as a high-value future entry).

## Discipline

Superpowers flow per task (plan → subagent implement → adversarial review → fix → re-review).
Surgical diffs. The packaged-app smoke gate is NOT optional and NOT last — build it early
(item 2) so items 1/3 are verified through it. Report format per CLAUDE.md after every
change. If a work item proves larger than expected, cut from the bottom of the list, never
compromise the gates. Leave RUN_STATE.md telling the owner exactly what his morning test
should show.
