# Council: Make It Real — 2026-07-10 (evening)

Four independent reports feed this council: two adversarial engineering audits grounded in this
repo and the RUNNING PACKAGED APP (connectors reality; product gaps), and two market research
sweeps (competitive landscape 2026; ethics/laws + attorney jobs-to-be-done). Reports in
`docs/council/2026-07-10-reports/` — every engineering claim carries file:line or live-endpoint
evidence, every market claim a source URL. This document is the synthesis: seat verdicts,
convergent findings, the owner's connector questions answered, and the mission for tonight's
sprint. Seats weighted per the owner: attorneys and practice owners speak first and loudest.

Owner brief this council answers: what have we achieved, what's good, what's bad, where are the
gaps; the questions we're not asking; the laws we're not thinking about; where our advantage is;
how we become a product attorneys love; why the connectors don't actually connect and which ones
matter; what tonight's sprint must do to move this toward a product firms can actually use.

---

## 1. Where we stand (context)

Shipped TODAY, this session: **v0.4.0, live as Latest** — the matter digest keystone. Ingest-time
fact extraction mechanically gated by the citation verifier (LLM proposes, `locate_span`
disposes), attorney-confirmed deadlines (the tool NEVER computes a date), instant matter overview
with every row cited and click-through highlighted. Gates: 63/63 present + 9/9 not-found + 0
rejected claims on an unchanged answer path; new G-DIG extraction gate passed at digest-v4
(parties 100%, amounts 100%, dates 86%, zero unverified spans stored); spot grade: zero
date_iso violations across 46 facts. Also this session: the release pipeline no longer hardcodes
the bundle version (a v0.4.0 build once stamped 0.3.2 — caught before publish).

## 2. Seat verdicts (each seat is deliberately critical)

**Maria — solo litigator. Verdict: the digest is the first thing in this app built for how I
actually work, and it dead-ends exactly where my malpractice policy starts caring.**
Opening a matter and seeing deadlines with the contract language quoted — that is the first
"this tool read my documents" moment this product has produced. But I confirm a deadline and
then... nothing. No calendar entry, no .ics, no reminder. Deadline errors are 19–34% of
malpractice claims (ABA's current figure: 22.87%) — the single largest cause. You built the
hard 90% (verified extraction, my-date-not-yours confirmation) and skipped the trivial 10%
(put it on my calendar) that makes it real. Same story in chat: I get a beautifully cited
answer and cannot copy it, print it, or drop it into a memo — the ONLY clipboard integration
in the entire app is your referral link (`app.js:2441`). That's a growth hack shipping before
the product. Verdict on the session's work: keep it. Verdict on the loop: close it tonight.

**Rosa — managing partner, 6-attorney firm. Verdict: I cannot buy a filing cabinet that only
accepts hand-fed paper.**
My firm's documents live in email, Dropbox, Zoom recordings, and our practice management
system. Your catalog page promises 28 connections; in the app my attorneys would install,
**zero of them work** — the shipped bundle contains no adapters at all
(`/connections/services` → `{"services":[]}` on the installed app). I don't care that the
source tree passes 189 connector tests; I run the DMG, not the repo. And this is the THIRD
time this pattern has shipped (WKWebView uploads, keychain, now connectors): tested at source,
broken in the bundle. Until a packaged-app smoke gate exists in the release recipe, every
release claim is unverified marketing. Fix the one-line packaging defect, yes — but the
institutional fix is the gate. Also: nobody in this firm uses a Mac exclusively; Windows
remains a standing blocker for firm sales.

**David — transactional attorney, data-loss averse. Verdict: the trust architecture is now
ahead of the trust EXPERIENCE.**
Under the hood this session was excellent: extraction that can only store verified spans,
review state that survives re-extraction, disposition that can't be resurrected by an in-flight
job. But the experience still leaks doubt in small ways the architecture doesn't deserve: the
first-run sample matter can refuse its own suggested question during the ~20s ingest race
(observed live: `Table 'chunks' was not found`); the Time Machine exclusion — a headline
privacy behavior — failed silently in a live run with no UI surface (`api.py:158-165`); and
the digest quietly says nothing when a document produced zero facts because Ollama was down
versus genuinely having none. Every one of these is a moment where an attorney's confidence is
decided. None is more than a day of work.

**Patricia — tech-skeptic solo. Verdict: for the first time I can say what this app does in one
sentence a lawyer believes. Now make the first five minutes prove it.**
"Open your matter and it already knows the parties, the money, and the deadlines — with the
page cited" is a sentence I'd repeat to colleagues. What I won't tolerate: clicking a
connector card that does nothing (I assume the whole app is fake), an update banner the day
after I installed (fine, once — but the changelog better read like English, no jargon), and
any date the machine "helpfully" computes for me. You got the last one right — hold that line
forever.

**Aisha — legal-tech reviewer. Verdict: you are, checkably, the only free local-first
verified-citation product in the market — and your README still shows last month's app.**
The whitespace is real: none of Clio Duo, CoCounsel, Spellbook, Harvey, Paxton, Smokeball,
MyCase, NetDocuments, or iManage runs inference on-device; Spellbook's "Most Private AI for
Lawyers" is zero-data-retention *contracts* on top of cloud APIs, and Paxton — the only
solo-accessible citation-verification competitor — is $499/user/month, cloud-only. Meanwhile
Stanford's RegLab keeps measuring 17–43% hallucination rates in incumbents, and *United
States v. Heppner* (S.D.N.Y. 2026) just voided privilege over consumer-AI chats because of the
vendor's privacy policy. You have a live federal case that IS your pitch. But your shop
window: `docs/demo.png` is the pre-digest design, the README feature list predates matters,
transcripts, connectors, AND the digest; the Product Hunt badge points at an app that has
tripled in capability since. If a reviewer downloads on the README's promise today, the gap
embarrasses you in the right direction — that's rare. Update it anyway; the overview IS the
screenshot now.

**Head of Engineering. Verdict: this session's discipline worked; the bundle discipline
doesn't exist. One line of PyInstaller config is currently worth more than any feature.**
Root cause, precisely: `connectors/__init__.py:63-77` discovers adapters via
`pkgutil.iter_modules` — dynamic imports PyInstaller cannot see — and neither spec collects
them, so the shipped registry is empty and `app.js` (correctly, honestly) hides Connect
buttons for an empty registry. `collect_submodules("connectors")` + data files unlocks 26 of
28 adapters in one build. Owner's architecture questions, answered plainly: **a desktop app
uses APIs exactly like a server does** — outbound HTTPS from the attorney's machine using a
key THEY paste (their account, their credential, sealed in the Keychain); we poll, list
changed documents, download, and push each file through the SAME upload path as a drag-drop,
landing in Unfiled with provenance, deduped; the attorney drags them onto matters
(`routes_kb` move — already built and tested). No cloud middleman, which is precisely why the
privilege story survives. The exceptions are OAuth-only vendors (Google, Microsoft, Clio,
Read AI): those need a registered app + a loopback-redirect flow we have NOT built (~3-6 days
each, plus vendor review outside our control) — they stay honestly Planned. My sprint asks,
in order: (1) the packaging fix, (2) a PACKAGED-APP SMOKE GATE in the release script (build →
launch the .app → assert `/connections/services` non-empty, uploads work, overview renders —
this kills the whole ship-broken-bundles class), (3) the first-run ingest race, (4) surface
TM-exclusion failure. Also flagged from the gaps audit: `retrieval.py:39` documents its own
~100k-chunk ceiling — not tonight's problem, but the "thousands of documents" claim has a
known cliff we should keep honest.

**Karpathy seat. Verdict: you built the right database this session. Resist the urge to build
another one — ship VERBS.**
The digest is the correct pattern: precompute at ingest, verify mechanically, render
instantly, zero read-time inference. The temptation now is more nouns — more fact types, more
panels, knowledge graphs, embeddings-of-embeddings. Wrong direction. The user's next unit of
value is a VERB on data you already trust: *export* this deadline to my calendar (an .ics
file is ~20 lines of code on top of `overview()`'s already-verified rows), *copy* this cited
answer, *import* from where documents already live. Also, from the extractor war this
afternoon: four prompt iterations, each failure mode mechanical and diagnosable
(constrained-decode stalls, field misrouting, over-extraction spirals) — the fix each time was
tighter bounds and deterministic fallbacks, never more model. Remember that. And the fact
that the eval caught a real packaging-adjacent bug (`document_type` legacy schema) is the
eval system paying rent.

**Of Counsel — ethics seat. Verdict: local-first now has a court case; deadlines need a
disclaimer; marketing needs a substantiation file.**
Three exposures we are not handling: (1) **silent omission on deadlines** — an attorney who
treats the Deadlines panel as complete will one day be missing the deadline we didn't
extract; the standard treatment (LawToolBox/CompuLaw class) is a persistent "verify against
the source; this is not a complete docket" line ON the panel, not buried in terms; (2)
**claim substantiation** — the FTC fined DoNotPay $193k for unsubstantiated "robot lawyer"
claims; every accuracy number in our copy must trace to our own eval artifacts (we actually
HAVE them — G-DIG, the golden gate — keep the receipts organized); (3) **retention schedules**
— client-file retention is 5–7 years by state (indefinite for criminal); disposition
certificates are built, but nothing encodes a jurisdiction policy. What our design already
satisfies, marketably: Rule 1.6(c) reasonable-efforts analysis collapses when data never
leaves the device, and *Heppner*'s privilege-destroying fact pattern (vendor policy permitting
training/disclosure) cannot occur here — say it carefully ("removes the vendor from the
privilege analysis"), never as "privilege can never be waived."

## 3. Convergent findings (what multiple seats hit independently)

1. **The gap between claimed and shipped is the product's biggest risk — and it's one line
   plus one gate.** Connectors: 0 of 28 in the bundle. Third instance of the
   source-tested/bundle-broken pattern. The packaged-app smoke gate is the highest-leverage
   engineering artifact this product can add. (Rosa, HoE, Patricia)
2. **Verified data with no verbs.** Deadlines can't reach a calendar; answers can't reach a
   memo. The wow is stranded one click from done. (Maria, Karpathy, gaps audit)
3. **The market lane is real, current, and citable**: only free local-first
   verified-citation product; *Heppner* + Stanford hallucination numbers + 22.87% of
   malpractice claims being deadline errors = a pitch made of receipts. (Aisha, ethics,
   market report)
4. **Trust is decided in small moments**: first-run race, silent TM failure, empty-state
   honesty. (David, Patricia)
5. **The shop window is stale**: README/demo.png predate the last three releases. (Aisha)

## 4. Questions we weren't asking (now we are)

- What happens the FIRST time the Deadlines panel misses a date an attorney relied on — and
  what did the panel say to set that expectation? (disclaimer + coverage honesty)
- Why would an attorney open this app on a day nothing is due? (the daily-habit question —
  connectors making it the place documents LAND is the strongest answer we have)
- Who is keeping the substantiation file that backs every number in our marketing copy?
- What is the uninstall/export-everything story an ethics-conscious buyer checks BEFORE
  committing client files? (matter export exists on the roadmap; make it a selling point)
- When documents change at the source (email thread grows, new Zoom recording), what keeps
  the matter current? (connectors' 30-min sync IS the answer — once they exist in the bundle)
- What does the Windows half of the small-firm market do while we're Mac-only?

## 5. Mission for tonight (owner-approval encoded): MAKE IT REAL

**Mission statement:** *Everything the app claims, the shipped app does. The attorney's
documents flow IN by themselves; verified deadlines flow OUT to the calendar; and the release
script refuses to ship a bundle that can't prove it.*

Sprint scope (priority order — see `docs/prompts/2026-07-10-next-session.md` for the
executable brief):

1. **Connectors, real.** Packaging fix (`collect_submodules` + data files, both specs) —
   verify in the BUILT app that the registry lists 26+ services and a real key-connect →
   import → Unfiled → drag-to-matter flow works end to end. Honest catalog pass: demote
   anything that can't work to Planned; note DocuSign/e-signature as a missing
   high-value entry for a future cycle.
2. **The packaged-app smoke gate.** Release script builds the .app, launches it against a
   scratch data dir, and asserts: server up, `/connections/services` non-empty, upload
   succeeds, overview renders, version matches `appversion.py`. A release cannot be cut
   without it. This is the institutional fix.
3. **Deadline → calendar.** "Add to calendar" (.ics download, standard fields, source quote
   in the notes) on every confirmed deadline row. Plus the ethics disclaimer line on the
   Deadlines panel.
4. **Copy/export the cited answer.** Copy-with-citations on chat answers (clipboard, and the
   groundwork for a future memo export).
5. **Trust polish:** first-run ingest race (suggested question waits for/streams readiness),
   TM-exclusion failure surfaced in Settings, digest empty-state distinguishes "no facts"
   from "couldn't read".
6. **Shop window:** README rewrite (current features, digest hero, *carefully worded*
   privacy/privilege positioning per ethics seat), fresh `docs/demo.png` (or short GIF) of
   the cream UI with the matter overview, site `softwareVersion` already bumped.
7. **Ship v0.4.1** through the FULL gate: 63/63 golden (engine untouched → expect identical),
   digest tests, the NEW packaged smoke gate, signed/notarized/stapled, Latest.

Explicitly OUT tonight: OAuth connector flows (Clio/Google/Microsoft — needs owner
registrations first), Windows build, retention-schedule policy layer, fact router / M-1
rewriting, cross-matter deadline dashboard. Queued, not forgotten.

**Definition of done for the night:** Jake wakes up, clicks "Update available v0.4.1", opens
Settings → Connectors, pastes ONE real API key, watches documents land in Unfiled, drags one
onto a matter, opens the matter, and puts a confirmed deadline onto his calendar — all without
touching a terminal.
