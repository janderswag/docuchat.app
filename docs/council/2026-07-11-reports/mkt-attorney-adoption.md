# Why Solo/Small-Firm Attorneys Adopt or Reject AI Contract-Review & Doc-Q&A Tools (2025–2026)

Role: market researcher. Date: 2026-07-11. Extends (does not repeat) `docs/council/2026-07-10-reports/market-2026.md` — competitor tiers, pricing ladder, adoption surveys, hallucination-sanction data, and local-first whitespace are established there and cross-referenced, not re-argued. This report answers the owner's Review & Compare questions specifically: what the review workflow looks like in competing tools, what output attorneys expect, what "speed to insight" means concretely, whether export is expected, and the honest steelman for why our Review & Compare tab would NOT be useful.

Every claim carries a source URL. Claims that rest on a single vendor-authored source are flagged.

---

## A. What the contract-review workflow actually LOOKS like in competing tools

### The dominant pattern: Word add-in → playbook → redlines via Track Changes

**Spellbook** (closest solo/small-firm comparable). The review flow: attorney opens the contract in Microsoft Word, runs Review; Spellbook applies the firm's playbook automatically ("a playbook loaded into Spellbook is automatically applied to every contract with no extra step required"), scans the incoming contract, flags deviations from the firm's positions, and recommends preferred or fallback language **as a suggested redline**. Edits land via Word's Track Changes "to make edits appear to be authored by the lawyer," and the attorney clicks Suggest Edit / accept / reject per item. It also flags "aggressive terms" and "missing clauses" and benchmarks terms against market ("Compare to Market," grounded in "hundreds of thousands of contracts"). Playbooks can be created by uploading an existing contract, describing criteria in plain language, or from prebuilt starters. Sources: [Spellbook review feature](https://spellbook.com/features/review), [contract playbook explainer](https://spellbook.com/learn/contract-playbook), [how lawyers use AI to review contracts](https://spellbook.com/learn/using-ai-to-review-contracts), [Lawyerist Spellbook review](https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/spellbook-review-artificial-intelligence-for-lawyers/).

**DraftWise (Markup).** Opening a contract in Word triggers automatic detection of agreement type; it "surfaces relevant precedents, playbooks, and previously negotiated positions — all without leaving your document," highlights issues inline as the lawyer works, and applies preferred language "with a single click." Distinctive: it **auto-curates playbooks from the firm's own precedent** rather than requiring manual playbook authoring. Claims 70% faster contract review (vendor-asserted). Sources: [DraftWise Markup announcement](https://www.draftwise.com/blog/draftwise-markup-sets-new-standard-in-legal-ai-with-intelligent-contract-review), [DraftWise product](https://www.draftwise.com/product), [Playbook Studio](https://www.draftwise.com/product/playbook-studio), [Lawyerist DraftWise review](https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/draftwise-review-artificial-intelligence-for-lawyers/), [Artificial Lawyer interview](https://www.artificiallawyer.com/2025/03/25/draftwise-claims-category-standard-with-upgraded-ai-contract-review-al-interview/).

**Gavel Exec (Gavel, formerly Lawyaw).** Word add-in plus (since April 2026) a web platform. In Word it "generate[s] suggested redlines across a full agreement and add[s] negotiation-ready comments" using playbooks and the firm's precedent, "with clear, traceable explanations." The web platform adds the batch/portfolio mode: it can "turn a folder of contracts into a structured review format, helping users extract terms, compare clauses, and spot inconsistencies across a portfolio" — i.e., a doc-x-clause grid like ours is a recognized format, but as the *portfolio* mode layered on top of the Word redline mode, not a replacement for it. Pricing: $160/user/mo ($1,740/yr). Lawyerist's reviewer praise is telling about the quality bar: "the redlines and markup are ones I actually want to accept" — implying competitors' suggestions often aren't. Sources: [Gavel Exec](https://www.gavel.io/exec), [Gavel Exec web launch](https://www.gavel.io/resources/ai-contract-review-software-for-lawyers-gavel-exec-is-now-on-web-and-word), [LawNext coverage](https://www.lawnext.com/2026/04/gavel-launches-web-based-ai-contract-platform-expanding-gavel-exec-beyond-its-word-add-in.html), [Lawyerist Gavel Exec review](https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/gavel-exec-review-artificial-intelligence-for-lawyers/).

**CoCounsel (Thomson Reuters).** The "Review Documents" skill takes up to 200 files, runs prompt-defined analysis, and returns results **in a customizable table** with hyperlinked footnotes carrying page citations. Output includes Summary and Conclusion sections, and downloads to **Excel or Word** (Excel recommended "to help with the organization of citations such as footnotes"). This is the closest mainstream analog to our doc-x-clause grid — note it is table + citations + export, and it feeds drafting workflows (demand letters, contracts). Sources: [TR help: Review Documents skill](https://www.thomsonreuters.com/en-us/help/cocounsel/legal/skills/skills-prompts-workflows/review-documents), [TR help: skills & workflows](https://www.thomsonreuters.com/en-us/help/cocounsel/legal/skills/skills-prompts-workflows), [Lawyerist CoCounsel review](https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/cocounsel-review-artificial-intelligence-for-lawyers/).

**Harvey (Vault review tables).** Enterprise-only (see market-2026.md) but sets the UX bar: each review-table **column is a prompt run across all files; each cell cites the specific passages it relied on**; users can open the doc previewer from a cell, re-run individual cells without regenerating columns, bulk verify/unverify rows, and flag cells; export goes to Excel with "verified cells as green and flagged cells as red" preserved, and workflow outputs export as **Word, Excel, or PowerPoint** — "a client-ready deliverable in your preferred docx format without any manual reformatting." Sources: [Harvey help: review tables](https://help.harvey.ai/articles/ask-questions-directly-in-review-tables), [Harvey Vault](https://www.harvey.ai/platform/vault), [Harvey: intake to deliverable](https://www.harvey.ai/blog/from-intake-to-deliverable-with-harvey), [Harvey help: workflow agents](https://help.harvey.ai/articles/assistant-workflows).

**Paxton.** Upload-based document analysis (not Word-native): fast processing, "highlighted risks and contextual authority links for every flagged area," source highlighting, Q&A against the uploaded set. Positioning is all-in-one assistant rather than redline engine. Sources: [Paxton contract review](https://www.paxton.ai/ai-contract-review), [Paxton document analysis](https://www.paxton.ai/document-analysis), [Lawyerist Paxton review](https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/paxton-ai-review-artificial-intelligence-for-lawyers/).

### Is Word really the attorney's native habitat? Verified, with one caveat

- Direct claims: "Lawyers spend up to six hours per day inside Microsoft Word"; Word is "the operating system of legal work... Every layer in the stack passes through Word at least once"; "60% to 80% of repeatable firm output" is produced in Word. **Caveat: these figures come from Infoware/Word LX, a vendor of Word tooling for law firms, with no external citation** — treat as directional. [Infoware Q1 2026 workflow-integration piece](https://infowaregroup.com/legal-tech-workflow-integration-2026/), [Infoware Word statistics post](https://infowaregroup.com/2024/08/09/3-statistics-you-should-know-about-microsoft-word-for-legal-professionals/) (also reports 77%+ share Word docs externally with clients).
- The stronger, structural evidence: **every major contract-review product ships as a Word add-in or exports to Word.** Spellbook, DraftWise, and Gavel Exec are Word add-ins first; Harvey built "Harvey for Word" and .docx deliverable export; CoCounsel exports Word/Excel; Smokeball's July 2026 Archie relaunch is "embedded in Word and Outlook" (market-2026.md). The revealed preference of the entire category is that review happens in, or ends in, Word. [Harvey for Word](https://help.harvey.ai/articles/harvey-for-word), [LawNext on Archie](https://www.lawnext.com/2026/07/two-years-after-launching-its-ai-assistant-archie-smokeball-rolls-out-the-next-generation-built-on-agentic-ai-and-embedded-in-word-and-outlook.html).

**Verdict: "Word is the native habitat" is confirmed for transactional review work.** The unit of value is a marked-up .docx the attorney can send to the counterparty or file, not an in-app panel.

---

## B. Why attorneys adopt — and why they churn/reject

### Adoption drivers (what's actually pulling people in)

1. **Time recovered on repeat contract types.** "Most users report saving 15-30 minutes per contract; at 10 contracts/month, that's 2.5-5 hours saved or $750-1,500 in recovered billable time." [AI Vortex Spellbook analysis](https://www.aivortex.io/legal/compare/is-spellbook-worth-it/). LegalOn customers report 70-85% time reduction (vendor-asserted). [LegalOn buyer's guide](https://www.legalontech.com/ai-contract-review-software).
2. **"Senior attorney over the shoulder" for juniors/generalists** — flagging risky clauses and catching issues before partner review; training value alone cited as justifying cost. [AI Vortex](https://www.aivortex.io/legal/compare/is-spellbook-worth-it/).
3. **Zero context-switch.** Spellbook's pitch — review "without switching windows or endless copy and paste" — and DraftWise's "without the frustrating task-switching" framing recur across the category. [Spellbook](https://spellbook.com/), [DraftWise Markup](https://www.draftwise.com/blog/draftwise-markup-sets-new-standard-in-legal-ai-with-intelligent-contract-review).
4. **Consistency/playbook enforcement across attorneys and matters** — encoding the firm's positions so review quality doesn't depend on memory. [Lawyerist Gavel Exec review](https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/gavel-exec-review-artificial-intelligence-for-lawyers/), [Spellbook playbooks](https://spellbook.com/learn/contract-playbook).
5. **Integration with tools they already trust is a stated buying criterion:** 43% of respondents prioritized "integration with trusted software"; 33% the provider's understanding of their firm's workflows. [Best Law Firms / AI adoption curve](https://www.bestlawfirms.com/articles/the-ai-adoption-curve-in-law/7196).

### Rejection & churn reasons (published, not speculative)

1. **Low contract volume makes it not worth it — the single clearest published anti-fit for solos.** "Spellbook is not worth it if you draft fewer than 5 contracts per month, your contracts are highly standardized, you primarily do litigation... or you're a solo practitioner who can get 80% of the value from Claude at $20/month." The $75-275/mo premium "buys you in-document integration... worth it at volume but not at low usage." [AI Vortex worth-it analysis](https://www.aivortex.io/legal/compare/is-spellbook-worth-it/), [AI Vortex pricing analysis](https://www.aivortex.io/legal/compare/spellbook-pricing-2026/).
2. **Accuracy distrust.** Non-users cite accuracy (43%) and data security (37%) as top concerns; 39% cite "lack of trust in AI results" as a barrier ([Best Law Firms](https://www.bestlawfirms.com/articles/the-disconnect-in-legal-ai-is-real-all-talk-no-payoff/7006), [ABA LTT 2026](https://www.americanbar.org/groups/law_practice/resources/law-technology-today/2026/whats-really-holding-law-firms-back-from-embracing-ai/)). Cross-ref market-2026.md: 75% hallucination fear (ABA), only 1% "extremely confident" in AI output (Filevine).
3. **No measured ROI.** "Six in 10 in-house professionals said they have seen no savings in time or money... because of generative AI use by outside lawyers," with "just under half" attributing the lack of savings to hallucinations/inaccuracies forcing re-verification. [Best Law Firms disconnect piece](https://www.bestlawfirms.com/articles/the-disconnect-in-legal-ai-is-real-all-talk-no-payoff/7006). Cross-ref market-2026.md: <33% of solo/small firms report AI-driven revenue gains (Clio).
4. **The redlining quality gap is independently measured.** Vals VLAIR (Feb 2025, the only major independent benchmark): on **redlining, the human lawyer baseline (79.7%) beat every AI tool tested** (Harvey top AI score reported as 65.0% on the Vals report page; LawNext's write-up cites Harvey Assistant 59.4% and Vincent 53.6% — figures differ between the two sources, flagged). Meanwhile AI beat lawyers decisively at **Document Q&A (Harvey 94.8% vs lawyer 70.1%)**, data extraction, summarization, and transcript analysis. Conclusion in the report: legal AI "should only be used for certain types of redlining tasks." [Vals VLAIR report](https://www.vals.ai/industry-reports/vlair-2-27-25), [Artificial Lawyer coverage](https://www.artificiallawyer.com/2025/02/27/vals-publishes-results-of-first-legal-ai-benchmark-study/), [LawNext on later Vals eval](https://www.lawnext.com/2025/10/vals-ais-latest-benchmark-finds-legal-and-general-ai-now-outperform-lawyers-in-legal-research-accuracy.html).
5. **"False sense of security" / lawyer-in-the-loop consensus.** AI output "appears authoritative... which can create a false feeling of safety"; the professional consensus is lawyer-in-the-loop with attorneys validating everything the AI extracted. If the attorney must still read every clause, a flag list adds a step rather than removing one. [Feldman & Feldman on AI contract risks](https://feldman.law/news/ai-contract-review-risks/), [Legal People Group, lawyer-in-the-loop](https://legalpeoplegroup.com/blogs/lawyer-in-the-loop-contract-review/), [Global Legal Law Firm](https://globallegallawfirm.com/chatgpt-for-contract-review-risks-why-you-still-need-a-lawyer/).
6. **Price** (cross-ref market-2026.md): Paxton called a "game-changer" but $499/user/mo "steep for a one-person firm" (Lawyerist); ABA GPSolo ran "CoCounsel for Small Firms: Smart Assistant or Costly Add-On?". Gavel Exec $160/user/mo. docuchat at free sidesteps this entirely — price is a rejection reason we don't have.
7. **Adoption-vs-implementation gap:** ~70% of legal professionals use general AI tools personally but only 34% of firms adopted legal-specific AI platforms; 54% of firms provide no AI training — tools that need configuration (playbooks, prompts) die in the gap. [NC Bar 2026](https://www.ncbar.org/2026/01/13/beyond-the-ban-why-your-law-firm-needs-a-realistic-ai-policy-in-2026/), [ABA LTT 2026](https://www.americanbar.org/groups/law_practice/resources/law-technology-today/2026/whats-really-holding-law-firms-back-from-embracing-ai/).

(Direct Reddit churn threads for the specific tools could not be surfaced via search this session; the churn evidence above is from published reviews, benchmark data, and surveys.)

---

## C. What "speed to insight" means concretely

**The category norm for a single contract is seconds to low single-digit minutes, and the leaders market sub-minute.**

- LegalOn's 2026 benchmark (vendor-run, but methodology published: 11 models, 3,282 contracts, 21 guidelines): "LegalOn completed a full contract review in **2.3 seconds** — 17X faster than Claude Opus 4.6." [LegalOn benchmark post](https://www.legalontech.com/post/best-ai-contract-review-tools).
- Independent Vals VLAIR timing: "Harvey Assistant is consistently the fastest, with CoCounsel also being extraordinarily quick, **both with sub-minute average response times**"; the slowest tool tested (Oliver) took "five minutes or more per query" and was called out for it. AI overall ran "six times faster than lawyers at the lowest end, and 80 times faster at the highest end." [Vals VLAIR](https://www.vals.ai/industry-reports/vlair-2-27-25).
- The oft-cited 2018 LawGeex study set the anchor early: lawyers averaged 92 minutes to review NDAs; the AI took 26 seconds. [Referenced in GC AI's 2026 guide](https://gc.ai/blog/ai-contract-review).
- Category marketing language is uniformly "in seconds"/"within minutes, AI returns a marked-up document with flagged risks and suggested redlines." [LegalOn buyer's guide](https://www.legalontech.com/ai-contract-review-software), [HyperStart ("under-a-minute first-pass")](https://www.hyperstart.com/blog/best-contract-review-software/).

**What competitors show during processing — the deeper lesson is granularity, not spinners.** Harvey's review tables decompose the job: each column-prompt runs per file, **each cell is an independently re-runnable, independently cited, independently verifiable unit**; the attorney can verify/flag rows while the rest runs, and re-run one cell without redoing the column. [Harvey help](https://help.harvey.ai/articles/ask-questions-directly-in-review-tables). Spellbook/DraftWise deliver findings inline as suggestions the attorney processes one at a time — there is no "wait for the whole report" moment at all.

**Implication for docuchat:** our POST /clauses/review — one synchronous blocking request running the whole checklist over local Ollama — is architecturally the *opposite* of the category pattern on two axes: total latency (local 7-8B inference across a full checklist is minutes-to-tens-of-minutes vs a sub-minute norm) and granularity (all-or-nothing vs per-clause incremental). Honest framing: docuchat can never win the raw-latency race against cloud GPU fleets, so it must win on **progressive delivery** (first clause result on screen in seconds, grid fills in cell by cell, usable and citable before completion) and **persistence** (a long-running review that survives navigation and is never re-paid). A multi-minute synchronous spinner with no partial results is the single most disqualifying UX gap versus every competitor examined.

---

## D. Do attorneys expect to EXPORT/save review work product? Yes — it's table stakes, and the formats are specific

1. **Every serious competitor exports.** CoCounsel Review Documents → **Excel or Word** download, with Excel recommended for citation organization. [TR help](https://www.thomsonreuters.com/en-us/help/cocounsel/legal/skills/skills-prompts-workflows/review-documents). Harvey → Excel (flag colors preserved) and Word/Excel/PowerPoint deliverables, "client-ready... in your preferred docx format without any manual reformatting." [Harvey help](https://help.harvey.ai/articles/ask-questions-directly-in-review-tables), [Harvey blog](https://www.harvey.ai/blog/from-intake-to-deliverable-with-harvey). Gavel Exec web → "structured review format" reports over folders of contracts. [Lawyerist](https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/gavel-exec-review-artificial-intelligence-for-lawyers/). Word-add-in tools (Spellbook/DraftWise) don't need export — the redlined .docx *is* the saved work product.
2. **The native deliverable formats a review feeds are well-defined legal genres:**
   - **Due diligence memo** — "the primary written deliverable that summarizes the findings... the document that the deal partner reads before the negotiation call, and the document the client uses to make the buy or walk-away decision." Findings grouped by issue type, ordered by materiality, highest risk first. [Mage Legal, how to write a DD memo](https://magelegal.com/blog/how-to-write-due-diligence-memo).
   - **Red-flag issues report** — Bloomberg Law publishes a standard template: "highlight 'red flag' legal issues... a succinct explanation of key legal issues," explicitly *not* covering every document reviewed. [Bloomberg Law issues-reporting template](https://pro.bloomberglaw.com/insights/contracts/ma-due-diligence-issues-reporting-template-2/).
   - **Redlined contract** — the negotiation-facing output (Section A).
3. **Why it matters economically:** work product that can't be saved can't be billed, delegated, attached to the matter file, or produced later to defend the attorney's diligence. An in-app-only review is, in the attorney's terms, not work product at all — it's a preview.

**Read on our gap:** the absence of any save/export from Review & Compare is not a missing convenience; it breaks the tool's connection to the two things attorneys are paid for (deliverables and defensibility). The good news: our cited doc-x-clause grid maps almost 1:1 onto the red-flag issues report and the CoCounsel/Harvey exportable review table — the formats already exist; we just don't emit them.

---

## E. Steelman: honest reasons our Review & Compare tab would NOT be useful to attorneys

Our tab: clause checklist + doc-x-clause grid, every cell cited to file+page+span, local-only, no cloud. The strongest case against it:

1. **It produces analysis, not work product.** The transactional attorney's job output is a redlined .docx or a client memo. Our tab ends where their job begins: it tells them a limitation-of-liability clause is missing but offers no preferred language, no fallback, no insertable edit, no memo. Every successful competitor terminates in Track Changes or a .docx/.xlsx deliverable ([Spellbook](https://spellbook.com/features/review), [Harvey](https://www.harvey.ai/blog/from-intake-to-deliverable-with-harvey), [TR](https://www.thomsonreuters.com/en-us/help/cocounsel/legal/skills/skills-prompts-workflows/review-documents)). Ours terminates in a panel.
2. **It's not in Word.** The whole category's revealed preference is Word-native review (Section A). Our flow forces the context-switch (export from Word → ingest → review in our app → manually re-find each issue back in Word) that Spellbook and DraftWise explicitly market against. [Spellbook](https://spellbook.com/), [DraftWise](https://www.draftwise.com/blog/draftwise-markup-sets-new-standard-in-legal-ai-with-intelligent-contract-review).
3. **It's slow in a sub-minute category, with the worst possible failure mode.** Sub-minute is the leaders' norm; the one benchmarked tool taking 5+ minutes was singled out as the laggard ([Vals](https://www.vals.ai/industry-reports/vlair-2-27-25)). Our synchronous, non-progressive, non-persistent request is slower AND delivers nothing until it delivers everything.
4. **The quality ceiling is documented — and we're below the tools that already fail it.** Independent benchmarking shows *frontier cloud* tools losing to human lawyers at contract review/redlining (lawyers 79.7% vs best AI ~59-65%) ([Vals](https://www.vals.ai/industry-reports/vlair-2-27-25)). A local 7-8B model will land materially below that. In review, a **false negative is a malpractice vector**: a checklist that misses a clause invites the "false sense of security" failure the profession explicitly warns about ([Feldman](https://feldman.law/news/ai-contract-review-risks/)). If the prudent attorney must therefore re-read the whole contract anyway, the tab saved zero time and added a step — which is exactly the no-ROI complaint driving churn ([Best Law Firms](https://www.bestlawfirms.com/articles/the-disconnect-in-legal-ai-is-real-all-talk-no-payoff/7006)).
5. **A generic checklist isn't the value; the firm's playbook is.** Competitors' review is animated by *the firm's own positions* — preferred language, fallbacks, precedent ([Spellbook playbooks](https://spellbook.com/learn/contract-playbook), [DraftWise auto-curated playbooks](https://www.draftwise.com/product/playbook-studio)). A fixed clause checklist tells an experienced transactional attorney what they already know ("does it have an indemnity clause?") and can't encode what they actually negotiate over (whose indemnity language, what caps).
6. **No save/export = not billable, not defensible, not delegable** (Section D). In its current form the review evaporates on navigation.
7. **Many solos don't have the workload shape.** The published anti-fit for Spellbook — fewer than 5 contracts/month, standardized contracts, or a litigation practice — describes a large share of solo practitioners ([AI Vortex](https://www.aivortex.io/legal/compare/is-spellbook-worth-it/)). For them a Review tab is a dead tab, and dead tabs erode trust in the rest of the product.
8. **Configuration dies at small firms.** 54% of firms provide zero AI training ([ABA LTT 2026](https://www.americanbar.org/groups/law_practice/resources/law-technology-today/2026/whats-really-holding-law-firms-back-from-embracing-ai/)); anything requiring checklist/playbook setup before first value will simply not get set up.

### What survives the steelman (so the council doesn't over-correct)

- **The doc-x-clause grid is a legitimate, recognized format — for the *portfolio/diligence* job, not the *negotiation* job.** Gavel's web batch review, Harvey's Vault review tables, and CoCounsel's review tables are all doc-x-clause grids; Bloomberg Law's red-flag issues report is its memo form. Our grid competes in the right genre if it's framed as "what's in this matter's contracts / what's missing across them" (diligence, intake, estate/lease/vendor portfolios) rather than "review this contract for negotiation."
- **Our two real advantages match the two strongest attorney anxieties** (market-2026.md §4-5): every cell mechanically span-verified (vs. the 17-43% hallucination rates and 1,745+ sanction cases) and local-only (ABA 512 / Heppner). No cloud grid can say either.
- **Vals is actually encouraging for our architecture's sweet spot:** AI decisively beats lawyers at document Q&A and extraction — which is what a cited clause-presence grid is — and loses at redlining, which we correctly do not attempt. Our scope, honestly framed ("locate and cite, never advise"), sits on the winning side of the benchmark.
- The fixes the evidence points to, in order: (1) progressive per-clause results with persistence (kills the blocking spinner), (2) export to .docx/.xlsx in the red-flag-report shape with citations preserved, (3) editable checklist = a lightweight playbook, teachable not learned. All three are workflow changes, not answer-engine changes — the frozen gate is untouched.

---

## Source list

**Review workflows / output formats**
- Spellbook Review — https://spellbook.com/features/review
- Spellbook playbooks — https://spellbook.com/learn/contract-playbook
- Spellbook, how lawyers use AI to review contracts — https://spellbook.com/learn/using-ai-to-review-contracts
- Lawyerist Spellbook review — https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/spellbook-review-artificial-intelligence-for-lawyers/
- DraftWise Markup — https://www.draftwise.com/blog/draftwise-markup-sets-new-standard-in-legal-ai-with-intelligent-contract-review
- DraftWise product / Playbook Studio — https://www.draftwise.com/product ; https://www.draftwise.com/product/playbook-studio
- Lawyerist DraftWise review — https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/draftwise-review-artificial-intelligence-for-lawyers/
- Artificial Lawyer, DraftWise interview — https://www.artificiallawyer.com/2025/03/25/draftwise-claims-category-standard-with-upgraded-ai-contract-review-al-interview/
- Gavel Exec — https://www.gavel.io/exec
- Gavel Exec web launch — https://www.gavel.io/resources/ai-contract-review-software-for-lawyers-gavel-exec-is-now-on-web-and-word
- LawNext, Gavel web platform — https://www.lawnext.com/2026/04/gavel-launches-web-based-ai-contract-platform-expanding-gavel-exec-beyond-its-word-add-in.html
- Lawyerist Gavel Exec review ($160/user/mo) — https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/gavel-exec-review-artificial-intelligence-for-lawyers/
- Thomson Reuters, Review Documents skill — https://www.thomsonreuters.com/en-us/help/cocounsel/legal/skills/skills-prompts-workflows/review-documents
- Thomson Reuters, skills/prompts/workflows — https://www.thomsonreuters.com/en-us/help/cocounsel/legal/skills/skills-prompts-workflows
- Lawyerist CoCounsel review — https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/cocounsel-review-artificial-intelligence-for-lawyers/
- Harvey review tables — https://help.harvey.ai/articles/ask-questions-directly-in-review-tables
- Harvey Vault — https://www.harvey.ai/platform/vault
- Harvey, intake to deliverable — https://www.harvey.ai/blog/from-intake-to-deliverable-with-harvey
- Harvey workflow agents / Word — https://help.harvey.ai/articles/assistant-workflows ; https://help.harvey.ai/articles/harvey-for-word
- Paxton contract review / document analysis — https://www.paxton.ai/ai-contract-review ; https://www.paxton.ai/document-analysis
- Lawyerist Paxton review — https://lawyerist.com/reviews/artificial-intelligence-in-law-firms/paxton-ai-review-artificial-intelligence-for-lawyers/

**Word-habitat**
- Infoware Q1 2026 workflow integration — https://infowaregroup.com/legal-tech-workflow-integration-2026/ (vendor-asserted, flagged)
- Infoware Word statistics — https://infowaregroup.com/2024/08/09/3-statistics-you-should-know-about-microsoft-word-for-legal-professionals/
- LawNext, Smokeball Archie in Word/Outlook — https://www.lawnext.com/2026/07/two-years-after-launching-its-ai-assistant-archie-smokeball-rolls-out-the-next-generation-built-on-agentic-ai-and-embedded-in-word-and-outlook.html

**Adoption / churn / benchmarks**
- AI Vortex, is Spellbook worth it — https://www.aivortex.io/legal/compare/is-spellbook-worth-it/
- AI Vortex, Spellbook pricing 2026 — https://www.aivortex.io/legal/compare/spellbook-pricing-2026/
- Vals VLAIR (Feb 2025) — https://www.vals.ai/industry-reports/vlair-2-27-25
- Artificial Lawyer, Vals first benchmark — https://www.artificiallawyer.com/2025/02/27/vals-publishes-results-of-first-legal-ai-benchmark-study/
- LawNext, Vals legal research eval — https://www.lawnext.com/2025/10/vals-ais-latest-benchmark-finds-legal-and-general-ai-now-outperform-lawyers-in-legal-research-accuracy.html
- Best Law Firms, legal AI disconnect (60% in-house no savings) — https://www.bestlawfirms.com/articles/the-disconnect-in-legal-ai-is-real-all-talk-no-payoff/7006
- Best Law Firms, AI adoption curve (43% integration priority) — https://www.bestlawfirms.com/articles/the-ai-adoption-curve-in-law/7196
- ABA LTT 2026, what's holding firms back — https://www.americanbar.org/groups/law_practice/resources/law-technology-today/2026/whats-really-holding-law-firms-back-from-embracing-ai/
- NC Bar 2026, realistic AI policy — https://www.ncbar.org/2026/01/13/beyond-the-ban-why-your-law-firm-needs-a-realistic-ai-policy-in-2026/
- Feldman & Feldman, AI contract risks — https://feldman.law/news/ai-contract-review-risks/
- Legal People Group, lawyer in the loop — https://legalpeoplegroup.com/blogs/lawyer-in-the-loop-contract-review/
- Global Legal Law Firm, AI contract review risks — https://globallegallawfirm.com/chatgpt-for-contract-review-risks-why-you-still-need-a-lawyer/

**Speed**
- LegalOn 2026 benchmark (2.3s, vendor-run) — https://www.legalontech.com/post/best-ai-contract-review-tools
- LegalOn buyer's guide — https://www.legalontech.com/ai-contract-review-software
- GC AI 2026 guide (LawGeex 92min vs 26s) — https://gc.ai/blog/ai-contract-review
- HyperStart (under-a-minute first pass) — https://www.hyperstart.com/blog/best-contract-review-software/

**Export / deliverable genres**
- Mage Legal, due diligence memo — https://magelegal.com/blog/how-to-write-due-diligence-memo
- Bloomberg Law, M&A issues reporting template — https://pro.bloomberglaw.com/insights/contracts/ma-due-diligence-issues-reporting-template-2/
- Thomson Reuters, due diligence checklist template — https://legal.thomsonreuters.com/en/insights/articles/what-due-diligence-checklist-template

**Flags:** Infoware six-hours-in-Word stat is vendor-asserted without external citation; LegalOn 2.3s is a vendor-run benchmark; Vals redlining figures differ between the Vals page (Harvey 65.0%) and LawNext (59.4%) — cite the range; AI Vortex is an affiliate-style comparison site, use for directional churn logic only; no first-person Reddit churn threads for these specific tools were retrievable this session.
