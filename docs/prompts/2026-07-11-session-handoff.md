# Session handoff — written 2026-07-11, closing the "Make It Real" session

_For the NEXT session: read RUN_STATE.md's top entry first, then this. Both are current as
of v0.4.2. Do not re-derive state from git archaeology; these two files are the state._

## Where the product is

v0.4.2 live as Latest. In three releases across one day: matter digest + attorney-confirmed
deadlines (0.4.0, gated 63/63 + G-DIG), connectors actually shipping + packaged-app smoke
gate + deadline .ics + copy-cited-answer + chat thread fix (0.4.1), real restart after
update + slash-command palette (0.4.2). The answer engine is UNTOUCHED since the v0.4.0
gate (63/63 + 9/9 + 0 rejected stands). Council synthesis + market/ethics/gaps/connectors
research: docs/council/2026-07-10-council-make-it-real.md and its reports dir.

## Owner actions pending (blockers others can't clear)

1. OAuth registrations (Clio Manage, NetDocuments, Microsoft Entra, Google, Read AI) —
   docs/2026-07-10-connector-registrations.md. Unlocks the Planned connector tier.
2. Real-account connector pass (paste one real key end-to-end).
3. Time Machine backup — still none configured. Standing risk.

## Queued backlog (council-ranked; do not start without owner priority call)

- OAuth loopback-redirect connector flow (~3-6 days/vendor AFTER registrations).
- Matter export/import (encrypted bundle) — the local sharing stepping-stone.
- M-1 query rewriting (stateless follow-ups fail today) — gated by new G-MT class.
- Fact router (digest steers retrieval) — full 63/63 + G-AGG gate cycle required.
- PRE-EXISTING apostrophe-in-href breakout in injectChips/renderAnswerHtml
  (app.js ~1140-1160) — same class we fixed in the overview; small fix + test.
- Windows build (build_windows.spec now collects connectors; needs owner box + Azure signing).
- Extractor v5 label-quality polish (list in eval/digest_spot_grade_v4.md).
- Jurisdiction retention-schedule policy layer; cross-matter "due this week";
  DocuSign/e-signature adapter (absent from catalog, high value).
- One-shot digest backfill → consider retry-on-Ollama-recovery.

## Verify-first next session (untested-in-anger surfaces)

- v0.4.1→v0.4.2 in-place update on the owner's machine: does the window now actually
  close and relaunch? (Launcher-owned relaunch's first real-world run. UI falls back to
  "Update installed. Quit and reopen docuchat." after 25s if not.)
- Slash palette in the packaged app: type "/", arrow keys, Enter; confirm Enter still
  sends normally when the palette is closed.
- Digest confirm flow in WKWebView (date input focus behavior).

## Hard-won lessons this session (do not relearn)

- Source tests prove NOTHING about the bundle: PyInstaller can't see pkgutil dynamic
  imports; the packaged-app smoke gate in build_macos.sh is now the enforcement — never
  SKIP_SMOKE a release.
- The packaged app is ONE process; a pending in-process SIGTERM never delivers while the
  main thread sits in the Cocoa run loop. Launcher owns lifecycle; markers over signals.
- Constrained decoding: small groups + num_predict caps; deterministic gate-side
  fallbacks over prompt begging; "extract EVERY" prompts cause over-extraction spirals.
- Adversarial review after EVERY task paid out 100%: nine reviews, nine real defects.
- Release recipe: version derives from appversion.py everywhere (spec once hardcoded it).
