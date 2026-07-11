# Ethics, Laws, and Attorney JTBD — Research Sweep for docuchat

Date: 2026-07-10
Scope: bar ethics rules on AI, confidentiality/privilege mechanics, docketing/retention/e-discovery duties, UPL and marketing-claims boundaries, and an attorney jobs-to-be-done reality check — all read against docuchat's actual design (local-first inference, verified citations, matter isolation, attorney-confirms-every-date deadline extraction, no deadline math performed by the tool).

---

## 1. Bar ethics on AI (current through 2026)

### ABA Formal Opinion 512 (July 29, 2024) — the baseline
The ABA Standing Committee on Ethics and Professional Responsibility issued the first national ethics guidance on generative AI. It maps GAI use onto five existing Model Rules rather than creating new ones:

- **Competence (Rule 1.1):** lawyers must understand a GAI tool's capabilities and limitations "to a reasonable degree" before using it, and must keep that understanding current as tools change.
- **Confidentiality (Rule 1.6):** lawyers must understand how a given tool ingests, stores, and potentially reuses/trains on data before inputting client information, and must put safeguards in place.
- **Communication (Rule 1.4)/informed consent:** may be required depending on how the tool is used and what data it touches (opinion does not mandate blanket disclosure — it's fact-specific).
- **Candor to the tribunal (Rule 3.3) / supervision (Rules 5.1, 5.3):** lawyers are responsible for verifying AI output before filing (the "hallucinated citations" problem) and for supervising subordinates' and even client use of AI tools.
- **Fees (Rule 1.5):** a lawyer may not bill client time saved by AI as if it were time spent, and generally may not charge clients for time spent learning a general-purpose AI tool (may charge to learn a tool the client specifically requested).

Sources: [ABA Formal Opinion 512 (PDF)](https://www.americanbar.org/content/dam/aba/administrative/professional_responsibility/ethics-opinions/aba-formal-opinion-512.pdf), [ABA news release](https://www.americanbar.org/news/abanews/aba-news-archives/2024/07/aba-issues-first-ethics-guidance-ai-tools/), [ABA Business Law Today summary](https://www.americanbar.org/groups/business_law/resources/business-law-today/2024-october/aba-ethics-opinion-generative-ai-offers-useful-framework/), [NCBE Bar Examiner summary](https://thebarexaminer.ncbex.org/article/fall-2024/generative-artificial-intelligence-tools/)

### State bar guidance (six states requested)

| State | Instrument | Key asks |
|---|---|---|
| **California** | State Bar "Practical Guidance for the Use of Generative AI in the Practice of Law" (Nov. 16, 2023; revised May 14, 2026) | Non-binding "guiding principles." Duty of competence/diligence — no overreliance, must apply independent judgment. Billing: may charge for time spent refining prompts/reviewing output, **must not** bill time saved. Confidentiality is paramount because GenAI platforms often reuse inputs for training. **2026 development:** the CA Supreme Court directed the State Bar (Aug. 22, 2025) to consider folding this guidance into the enforceable Rules of Professional Conduct — proposed amendments are in public comment now, which would make AI-specific obligations disciplinable, not just aspirational. |
| **Florida** | Ethics Opinion 24-1 (Jan. 19, 2024, advisory/non-binding) | Confidentiality — must research a tool's data retention/sharing/self-learning policies before use. Lawyer remains responsible for all output. No improper billing (e.g., double-billing AI-accelerated work). Advertising restrictions apply to AI marketing claims. |
| **New York** | NYSBA Task Force on AI Report (adopted by House of Delegates, April 6, 2024) | Frames most AI questions as resolvable under existing competence/confidentiality/independent-judgment rules — **no new disclosure/consent mandate** (task force concluded existing duties already cover it, diverging from PA's explicit-consent stance). |
| **Texas** | Professional Ethics Committee Opinion 705 (Feb. 2025), from the Taskforce for Responsible AI in the Law (TRAIL) | Four obligations: competence (understand how the tool functions), confidentiality (watch for third-party data sharing), verification (independently check all AI output before use), fair billing (efficiency gains must flow to the client under hourly billing). |
| **New Jersey** | NJSBA Task Force on AI and the Law report | Practical guidance; specifically flags algorithmic bias risk — "AI systems trained on biased data... can exacerbate existing discriminatory practices" — and tells lawyers to vet tools before adoption. |
| **Pennsylvania** | Joint Formal Opinion 2024-200 (PA Bar + Philadelphia Bar, May 22, 2024) | Same competence/confidentiality core, **plus** two stricter asks than most states: (1) explicit client informed consent when AI benefits outweigh risks, and (2) mandatory disclosure of AI use in court filings — a filing requirement, not a best practice. |

Sources: [Cal. Practical Guidance PDF](https://www.calbar.ca.gov/Portals/0/documents/ethics/Generative-AI-Practical-Guidance.pdf), [CLA summary](https://calawyers.org/privacy-law/california-state-bar-releases-guidance-on-use-of-genai-in-practice-of-law/), [Cal. proposed RPC amendments](https://www.calbar.ca.gov/public/public-meetings-comment/public-comment/public-comment-archives/2026-public-comment/proposed-amendments-rules-professional-conduct-related-artificial-intelligence), [Fla. Op. 24-1](https://www.floridabar.org/etopinions/opinion-24-1/), [Hinshaw summary](https://www.hinshawlaw.com/en/insights/lawyers-for-the-profession-alert/florida-bar-advisory-opinion-24-1-gives-green-light-to-generative-ai-use-by-lawyers-with-four-ethical-caveats), [NYSBA Task Force Report (PDF)](https://nysba.org/wp-content/uploads/2022/03/2024-April-Report-and-Recommendations-of-the-Task-Force-on-Artificial-Intelligence.pdf), [Texas Op. 705](https://www.legalethicstexas.com/resources/opinions/opinion-705/), [Texas Bar Blog summary](https://blog.texasbar.com/2025/04/articles/ethics/ethics-opinion-offers-principles-for-lawyers-ethical-use-of-ai/), [NJSBA Task Force Report (PDF)](https://njsba.com/wp-content/uploads/2025/12/NJSBA-TASK-FORCE-ON-AI-AND-THE-LAW-REPORT-final.pdf), [PA/Philly Joint Formal Op. 2024-200 (PDF)](https://www.ebglaw.com/assets/htmldocuments/noindex/PA%20Bar%20Joint%20Formal%20Opinion%202024-200%20May%2022%202024_%20ETHICAL%20ISSUES%20REGARDING%20THE%20USE%20OF%20ARTIFICIAL%20INTELLIGENCE.pdf)

### What local-only inference satisfies automatically vs. still leaves on the attorney

**Satisfied automatically by local inference:**
- Data does not leave the attorney's machine to a third-party AI vendor, so the Rule 1.6(c)/confidentiality "how does the tool use my data, does it train on it, does it share with third parties" inquiry that every one of these opinions requires (CA, FL, TX, PA, NJ, NY) collapses to "it doesn't leave the device" — no vendor privacy policy audit needed, no BAA/DPA negotiation needed.
- No cloud-provider retention/training risk of the kind that produced the privilege-waiver finding in *United States v. Heppner* (see §2) — there is no third party in the data path to hold the information at all.

**Still required of the attorney, tool or no tool:**
- Competence (Rule 1.1) — attorney still must understand docuchat's capabilities/limits (including its citation-verification and non-computation-of-deadlines design) and keep that understanding current.
- Verification/candor (Rule 3.3) — attorney must independently check every AI-surfaced fact, citation, and extracted date before relying on or filing it. This is exactly docuchat's design bet (verified citations, attorney confirms every date) but it is a *design choice that matches the ethics rule*, not a substitute for the attorney doing it.
- Billing discipline (Rule 1.5) — must not bill time saved by the tool as billed time; this is a firm practice issue docuchat cannot enforce technically.
- Disclosure/consent — jurisdiction-dependent (PA requires it explicitly under some circumstances; NY/CA do not mandate it categorically). A local tool doesn't remove this requirement; it just makes the underlying risk being disclosed lower.

---

## 2. Confidentiality/privilege mechanics

**Model Rule 1.6(c)** requires "reasonable efforts to prevent the inadvertent or unauthorized disclosure of, or unauthorized access to, information relating to the representation of a client." Recent state-bar opinions (NY, CA, FL, IL, and others) are converging on reading this to mean the firm's confidentiality controls must extend through the AI processing path — difficult when a third-party vendor controls that path (managed/cloud AI), straightforward when there is no third party (local).

Source: [Fishman Haygood summary of Rule 1.6 & GenAI](https://www.fishmanhaygood.com/resources/ethical-rules-for-using-generative-ai-in-your-practice-model-rule-1-6-confidentiality/), [iBL blog on Rule 1.6-compliant AI](https://ibl.ai/blog/aba-model-rule-1-6-compliant-ai)

**The load-bearing case: *United States v. Heppner*** (S.D.N.Y., Judge Rakoff, ruling reported Feb.–March 2026) — the first federal ruling squarely on AI-chat privilege.
- Holding: a criminal defendant's written exchanges with Claude were **not** protected by attorney-client privilege or work product.
- Privilege reasoning: communications were not "between a client and his or her attorney" (an AI is not an attorney) and were not "intended to be" or "in fact" kept confidential, because Anthropic's consumer privacy policy permits data collection, model training on inputs/outputs, and disclosure to third parties including "governmental regulatory authorities" — the court found this "fatally compromised" any reasonable expectation of confidentiality.
- Work-product reasoning: the AI queries were the defendant's own initiative, not made at counsel's direction, so there was no nexus to counsel's litigation strategy — dispositive against work-product protection.
- **Important limit:** the court did NOT hold that generative-AI use categorically waives privilege. It expressly left open (1) whether an *attorney's own* use of GenAI to prepare work product would be protected, (2) whether the analysis changes for a non-public/enterprise AI tool, and (3) whether a client using AI *at counsel's direction* could claim protection over the output.

Sources: [Harvard Law Review Blog](https://harvardlawreview.org/blog/2026/03/united-states-v-heppner/), [McDermott Will & Emery](https://www.mcdermottlaw.com/insights/using-ai-without-waiving-privilege-lessons-from-heppner/), [Orrick](https://www.orrick.com/en/Insights/2026/03/Court-Rules-AI-Conversations-Are-Not-Privileged-What-United-States-v-Heppner-Means-for-You), [Washington Legal Foundation](https://www.wlf.org/2026/04/27/publishing/united-states-v-heppner-use-of-generative-ai-can-waive-privileges/), [Venable](https://www.venable.com/insights/publications/2026/02/ai-privilege-and-the-heppner-ruling-what-the-court), [Verdict/Justia commentary](https://verdict.justia.com/2026/03/30/the-first-federal-ai-privilege-ruling-gets-the-right-result-for-the-wrong-reasons), [Bloomberg Law](https://news.bloomberglaw.com/legal-exchange-insights-and-commentary/heppner-shows-attorney-client-privileges-fragility-in-ai-era)

**Can we categorically say "local-only is safer"?** Yes, defensibly, on the specific mechanism *Heppner* turned on: the court's finding hinged entirely on Anthropic's *consumer* privacy policy permitting training/disclosure to third parties. A tool that performs inference locally, with no data transmitted to any vendor, removes that specific failure mode by construction — there is no vendor privacy policy to "fatally compromise" confidentiality because there is no vendor in the loop. This is a defensible, narrow, factual marketing claim ("your documents never leave your machine, so there is no third-party privacy policy that can compromise confidentiality the way *Heppner* found") — it should **not** be oversold as "AI use with docuchat can never waive privilege," since privilege law also turns on attorney conduct (was this prepared at counsel's direction, was it intended to be confidential, etc.) that a local tool cannot itself guarantee.

---

## 3. Duties that touch docuchat's features directly

### Docketing/calendaring standard of care
- Missed deadlines are consistently reported as the single largest driver of legal malpractice claims. The ABA Standing Committee on Lawyers' Professional Liability's quadrennial "Profile of Legal Malpractice Claims" attributes roughly **22.87%** of claims to administrative errors (calendaring/clerical/procrastination category) in the 2020–2023 edition; commentary broadly cites administrative/calendaring failures as approaching a quarter to over a third of all claims depending on the period measured, with the category trending down slightly over recent editions.
- Standard-of-care mechanics: courts generally treat a missed deadline as establishing breach *per se* — i.e., the missed deadline itself is close to conclusive evidence the standard of care wasn't met, shifting the real fight to causation/damages.
- Commercial deadline-calculation tools (LawToolBox, CompuLaw) do not warrant accuracy: LawToolBox's own disclaimer states users rely on calculated dates "at their own risk," disclaims warranties of accuracy/fitness for purpose, and directs users to "call the court specific to their filing to verify any date calculation." This is the existing industry norm docuchat's "attorney confirms every date, tool never computes deadline math" design already matches — and arguably exceeds, since docuchat doesn't even attempt the computation (removing an entire failure surface these commercial tools carry).
- **Liability angle for docuchat specifically:** surfacing an *extracted* date (e.g., "this document states a response is due by X") is lower-risk than *computing* a deadline (e.g., applying court rules to derive a due date), because extraction is representing what a document says, not asserting a legal conclusion about what's owed. But if docuchat ever misses/misreads a date in the source document (OCR error, missed page, wrong document version) and the attorney relies on the omission ("no deadline flagged") rather than an affirmative wrong answer, that's still a real exposure — silence-as-signal is at least as dangerous as a wrong answer. Recommend an explicit, persistent UI disclaimer that absence of a flagged date is not confirmation that no deadline exists, styled after the LawToolBox model above.

Sources: [ABA claims profile discussion (Minn Lawyer)](https://minnlawyer.com/2025/10/21/legal-malpractice-trends-aba-epic-lockton-2020-2023/), [TLIE on scheduling errors](https://www.tlie.org/resource/scheduling-errors-and-legal-malpractice), [CARET Legal on missed deadlines](https://caretlegal.com/blog/malpractice-for-missed-deadlines-a-litigators-constant-fear-how-to-curb-it/), [LawToolBox Deadline Calculator (disclaimer)](https://lawtoolbox.com/deadline-calculator/), [Aderant CompuLaw](https://www.aderant.com/solutions-compulaw/)

### Document retention rules (state record-retention for client files)
No single national number — ABA Model Rule 1.15 sets a **5-year** floor for trust/financial records post-termination; most states land in a **5–7 year** range for full client files (e.g., Washington and Illinois use 7 years; North Carolina and New Hampshire use ~6 years; LA County Bar opines 5 years minimum for civil files). Criminal defense files are frequently recommended for indefinite/life-of-client retention given habeas/post-conviction exposure. Practical implication for docuchat: matter isolation + local storage is an asset here (no ambiguity about a third-party vendor's own retention/deletion schedule interacting with the firm's obligations), but docuchat itself doesn't yet appear to encode jurisdiction-specific retention schedules — that's a firm policy layer, not something the tool should silently assume.

Sources: [WSBA Document Retention Guide](https://wsba.org/for-legal-professionals/member-support/practice-management-assistance/guides/document-retention-guide), [LeanLaw retention guide](https://www.leanlaw.co/blog/a-guide-to-document-retention-policies-how-long-must-you-keep-closed-client-files/), [NH Bar file retention guidelines](https://www.nhbar.org/file-retention-guidelines/), [NC State Bar RPC 209](https://www.ncbar.gov/for-lawyers/ethics/adopted-opinions/rpc-209/)

### Litigation hold / spoliation duties
- Common-law duty to preserve is triggered when litigation is "pending or reasonably foreseeable" (or by an independent statutory/contractual obligation) — well before a case is filed.
- **FRCP 37(e)** (2015 amendment) is the controlling federal standard for ESI specifically: if ESI that should have been preserved is lost because a party failed to take "reasonable steps" to preserve it, and it can't be restored/replaced, the court may (a) order curative measures no greater than necessary upon a finding of prejudice, or (b) — only upon a finding of **intent to deprive** — apply an adverse-inference instruction, presumption, or terminating sanction. Critically, 37(e) is **not** a strict-liability rule: it provides a "genuine safe harbor" for parties that took reasonable steps, even if ESI is ultimately lost; negligence alone can defeat the "reasonable steps" finding but doesn't itself trigger the harshest (intent-based) sanctions.
- Relevance to docuchat's legal-hold + disposition-cert features: the actual standard being tested by courts is "reasonable steps," not perfection — a documented, systematic hold-and-disposition-certification workflow is exactly the kind of evidence that supports a "reasonable steps were taken" finding under 37(e), which is the strongest defensive posture available.

Sources: [Duke Judicature — Rule 37(e) explainer](https://judicature.duke.edu/articles/rule-37e-the-new-law-of-electronic-spoliation/), [Duke Judicature — amended 37(e) update](https://judicature.duke.edu/articles/amended-rule-37e-whats-new-and-whats-next-in-spoliation/), [Everlaw legal holds guide](https://www.everlaw.com/blog/ediscovery-best-practices/guide-to-legal-holds/), [Boston Bar Journal on 37(e)](https://bostonbar.org/journal/the-impact-of-recent-revisions-to-fed-r-civ-p-37e-electronic-spoliation/)

### E-discovery competence — Cal. Formal Opinion 2015-193
Establishes that competence (duty applies generally, not just in CA) requires, at minimum: assessing e-discovery issues at the *outset* of a case, understanding how the client's ESI systems/storage work, advising on preservation/collection, identifying custodians, and handling data without compromising its integrity. An attorney lacking this competence has exactly three options: (1) get up to speed before it's needed, (2) associate with/consult a technically competent person, or (3) decline the representation. Association with a consultant does **not** discharge the attorney's own duty to supervise — including supervising the client's own IT/document handling; delegation to "the client's IT department" is explicitly called out as insufficient.

Source: [Cal. Formal Op. 2015-193 (PDF)](https://www.calbar.ca.gov/Portals/0/documents/ethics/Opinions/CAL%202015-193%20%5B11-0004%5D%20(06-30-15)%20-%20FINAL.pdf), [SF Bar Association summary](https://www.sfbar.org/blog/electronically-stored-information-and-the-duty-of-competence/)

---

## 4. What docuchat must not do

### UPL boundary — information vs. advice
The consistent line across sources: **legal information** = general explanation of what the law says (protected, not UPL); **legal advice** = applying law to a specific person's specific facts and recommending a course of action (UPL if rendered by a non-lawyer / non-lawyer-controlled system to an end client). The "uncrossable threshold" framing: a tool crosses into UPL territory when it moves from comparative/general information to a tailored legal conclusion about a specific user's specific situation. A cited "Tool Not Advisor" architecture pattern — surface options, flag issues, explain what clauses/provisions typically mean, but never recommend a specific course of action, paired with explicit scope disclaimers and routing to counsel — maps closely to docuchat's actual design (verified citations to source documents, attorney confirms conclusions, no deadline math). Because docuchat is attorney-facing (not consumer-facing direct-to-client), the core UPL risk is lower than for a consumer chatbot, but the same information/advice line still governs how any output should be phrased (describe what a document says and cite it; do not phrase output as "you should do X").

Sources: [AI Legal Authority — UPL boundaries overview](https://ailegalauthority.com/ai-unauthorized-practice-of-law/), [Thomson Reuters Institute — AI and UPL regulation](https://www.thomsonreuters.com/en-us/posts/government/ai-impacts-unauthorized-practice-of-law/), [Richmond JOLT — AI and UPL](https://jolt.richmond.edu/is-your-artificial-intelligence-guilty-of-the-unauthorized-practice-of-law/)

### FTC / state AI-claims enforcement — can we say "AI-powered legal analysis"?
The FTC's "Operation AI Comply" is an active enforcement program against "AI-washing" — false, misleading, or unsubstantiated AI capability claims. The clearest legal-tech precedent: **FTC v. DoNotPay** (settled Jan. 2025) — DoNotPay marketed itself as "the world's first robot lawyer"; FTC found the claims misleading/unsubstantiated/exaggerated, imposed a **$193,000** fine plus ongoing advertising restrictions. The operative rule: companies must have a "reasonable basis" — competent, reliable evidence (testing data, validation studies, benchmarks) — for every AI performance claim, explicit or implied, before making it. Practical takeaway for docuchat marketing copy: "AI-powered legal analysis" is fine as a factual description of the mechanism; claims implying accuracy guarantees, replacement of attorney judgment, or "robot lawyer"-style capability claims are exactly the pattern the FTC has already fined once in this exact vertical. Any claim about citation accuracy, deadline-extraction accuracy, etc. should be substantiated (internal test data) before being used in marketing.

Sources: [FTC press release — Operation AI Comply crackdown](https://www.ftc.gov/news-events/news/press-releases/2024/09/ftc-announces-crackdown-deceptive-ai-claims-schemes), [Lathrop GPM on FTC AI enforcement](https://www.lathropgpm.com/insights/transparency-and-ai-ftc-launches-enforcement-actions-against-businesses-promoting-deceptive-ai-product-claims/), [Legal.io — DoNotPay UPL/FTC suit](https://www.legal.io/articles/5798485/OpenAI-Sued-for-Unauthorized-Practice-of-Law-via-ChatGPT), [Benesch — Operation AI Comply one year later](https://www.beneschlaw.com/insight/one-year-in-ftcs-operation-ai-comply-continues-under-new-administration-signaling-enduring-enforcement-focus/)

### Pending/enacted state AI statutes touching legal tools (as of July 2026)
- **Colorado AI Act (SB24-205):** originally set to require high-risk-AI developer/deployer obligations (risk management program, impact assessments, consumer notice/appeal rights for "consequential decisions") starting Feb. 1, 2026. Colorado then **repealed and replaced** the framework via **SB 189** (signed May 14, 2026), delaying the effective date to **Jan. 1, 2027** and stripping out the duty-of-care/algorithmic-discrimination framework, deployer risk-management/impact-assessment mandates, and AG reporting obligations that were in the original law. Net effect: materially weaker than originally drafted, and not yet in force. If docuchat's deadline-extraction or matter-triage features were ever read as "consequential decision" automation for CO clients, this is the statute to watch as it's rewritten.
- **California:** SB 942 (AI Transparency Act, content-provenance/labeling) applies only to generative-AI platforms with **1M+ monthly visitors** — docuchat, as a local desktop tool for solo attorneys, is almost certainly out of scope on user-count grounds alone, and its effective date has itself been pushed to Aug. 2, 2026 (AB 853). No CA statute found that specifically targets legal-document AI tools by name; the operative CA-specific risk is the State Bar's rulemaking (§1 above) turning practical guidance into enforceable Rules of Professional Conduct.

Sources: [Colorado SB24-205 text](https://leg.colorado.gov/bills/sb24-205), [Law and the Workplace — SB189 rewrite](https://www.lawandtheworkplace.com/2026/04/colorado-takes-a-major-step-towards-rewriting-its-ai-law-as-its-effective-date-approaches/), [Norton Rose Fulbright — CO AI law revision](https://www.nortonrosefulbright.com/en-us/knowledge/publications/18733d31/colorado-enacts-revised-ai-law), [Troutman — CO repeal/replace](https://www.troutmanprivacy.com/2026/05/colorado-legislature-passes-bill-to-repeal-and-replace-colorado-ai-act/), [CA SB 942 bill text](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB942), [Pillsbury — new CA AI laws 2026](https://www.pillsburylaw.com/en/news-and-insights/new-california-ai-laws.html)

---

## 5. Attorney JTBD reality check

### Where the hours actually go (solo/small firm)
- Average utilization (billable hours ÷ total hours worked) for **solo** firms is **~26%**, vs. ~45% at large firms — solo attorneys carry disproportionate administrative burden. (Clio 2025 Legal Trends Report)
- Firm-wide average: lawyers bill **~2.9 of 8 hours** in a workday (~37% utilization); the remaining 5+ hours go to administration, business development, non-billable client service, and firm management.
- A separate Thomson Reuters survey found **45% of solo/small-firm time** goes to administrative tasks specifically (invoicing, intake paperwork, phone, payment processing) — not legal work at all.
- Solo/small firms carry an average of **93 days** of unbilled/uncollected work outstanding at any time.

### Ranked JTBD by hours/pain (solo litigator/transactional attorney) — synthesized from the above plus AI-adoption survey data
1. **Administrative/non-billable overhead** (intake, billing, phone, practice management) — largest single time sink (45% of time per Thomson Reuters), but least "legal" in nature and the least differentiated JTBD for a document-intelligence tool.
2. **Finding facts in documents / document review** — the JTBD with the clearest, most-measured AI time-savings data (see below); this is squarely docuchat's core use case.
3. **Drafting** — second most commonly cited AI use case in adoption surveys; large reported productivity multiples in Am Law 100 studies, though those are large-firm/large-matter numbers, not solo-practice-representative.
4. **Chronologies / timeline construction** — a sub-task of document review, not separately measured in the surveys found, but repeatedly named as one of the most tedious high-value-if-automated tasks in practitioner commentary (folds into #2).
5. **Deadline tracking / calendaring** — lower time-cost than document review day-to-day, but the highest *tail-risk* item (largest cause of malpractice claims per §3) — low hours, disproportionate downside.
6. **Billing** — administrative, not a "the tool saves me research time" JTBD; folds into #1.

### Published time-savings for document-QA-type tools specifically
- Thomson Reuters (2025 Future of Professionals research): AI tools have the *potential* to save lawyers up to **~240 hours/year** across routine tasks; among lawyers already using AI, **77% apply it to document review** specifically — the single most common use case reported.
- Thomson Reuters 2024 data: AI saved lawyers an average of **~4 hours/week** in 2024.
- Clio 2024 Legal Trends: **82%** of AI-using firms reported greater productivity; **65%** saved up to 5 hours/week; **62%** reported 6–20% weekly time savings.
- Large-firm case study (Everlaw/Am Law 100): a 3-attorney team review of 126,000 documents used AI coding suggestions to accelerate production review — directionally consistent with "document review is where AI time-savings are most concretely measured," though this specific large-scale/large-firm number is not representative of solo practice.
- Caveat: most of the "hours saved" figures above are self-reported survey data (Thomson Reuters, Clio), not controlled studies — useful directionally, not to be quoted as precise/independently verified numbers in docuchat marketing without attribution.

Sources: [Clio 2025 Legal Trends highlights](https://www.clio.com/blog/solo-small-law-firms-highlights-2025-legal-trends/), [Clio 2024 Legal Trends for solo/small firms](https://www.clio.com/blog/solo-small-law-firms-2024-legal-trends/), [Clio KPI benchmarks](https://www.clio.com/resources/legal-trends/benchmarks/), [Thomson Reuters — AI-driven future of legal efficiency (PDF)](https://www.thomsonreuters.com/en-us/posts/wp-content/uploads/sites/20/2025/04/The-AI-driven-future_2025.pdf), [Thomson Reuters Future of Professionals analysis](https://www.thomsonreuters.com/en-us/posts/legal/future-of-professionals-report-analysis-law-firm-economics/), [Everlaw — 32.5 days/year saved report](https://www.everlaw.com/blog/ai-and-law/lawyers-report-saving-up-to-32-5-working-days-per-year-with-generative-ai/), [Everlaw Am Law 100 case study](https://www.everlaw.com/blog/case-studies/am-law-100-firm-slashed-doc-review-time-by-two-thirds-with-genai/), [Embroker — solo law firm statistics](https://www.embroker.com/blog/solo-law-firm-statistics)

---

## Full source list (deduplicated)

1. https://www.americanbar.org/content/dam/aba/administrative/professional_responsibility/ethics-opinions/aba-formal-opinion-512.pdf
2. https://www.americanbar.org/news/abanews/aba-news-archives/2024/07/aba-issues-first-ethics-guidance-ai-tools/
3. https://www.americanbar.org/groups/business_law/resources/business-law-today/2024-october/aba-ethics-opinion-generative-ai-offers-useful-framework/
4. https://thebarexaminer.ncbex.org/article/fall-2024/generative-artificial-intelligence-tools/
5. https://www.calbar.ca.gov/Portals/0/documents/ethics/Generative-AI-Practical-Guidance.pdf
6. https://calawyers.org/privacy-law/california-state-bar-releases-guidance-on-use-of-genai-in-practice-of-law/
7. https://www.calbar.ca.gov/public/public-meetings-comment/public-comment/public-comment-archives/2026-public-comment/proposed-amendments-rules-professional-conduct-related-artificial-intelligence
8. https://www.floridabar.org/etopinions/opinion-24-1/
9. https://www.hinshawlaw.com/en/insights/lawyers-for-the-profession-alert/florida-bar-advisory-opinion-24-1-gives-green-light-to-generative-ai-use-by-lawyers-with-four-ethical-caveats
10. https://nysba.org/wp-content/uploads/2022/03/2024-April-Report-and-Recommendations-of-the-Task-Force-on-Artificial-Intelligence.pdf
11. https://www.legalethicstexas.com/resources/opinions/opinion-705/
12. https://blog.texasbar.com/2025/04/articles/ethics/ethics-opinion-offers-principles-for-lawyers-ethical-use-of-ai/
13. https://njsba.com/wp-content/uploads/2025/12/NJSBA-TASK-FORCE-ON-AI-AND-THE-LAW-REPORT-final.pdf
14. https://www.ebglaw.com/assets/htmldocuments/noindex/PA%20Bar%20Joint%20Formal%20Opinion%202024-200%20May%2022%202024_%20ETHICAL%20ISSUES%20REGARDING%20THE%20USE%20OF%20ARTIFICIAL%20INTELLIGENCE.pdf
15. https://www.fishmanhaygood.com/resources/ethical-rules-for-using-generative-ai-in-your-practice-model-rule-1-6-confidentiality/
16. https://ibl.ai/blog/aba-model-rule-1-6-compliant-ai
17. https://harvardlawreview.org/blog/2026/03/united-states-v-heppner/
18. https://www.mcdermottlaw.com/insights/using-ai-without-waiving-privilege-lessons-from-heppner/
19. https://www.orrick.com/en/Insights/2026/03/Court-Rules-AI-Conversations-Are-Not-Privileged-What-United-States-v-Heppner-Means-for-You
20. https://www.wlf.org/2026/04/27/publishing/united-states-v-heppner-use-of-generative-ai-can-waive-privileges/
21. https://www.venable.com/insights/publications/2026/02/ai-privilege-and-the-heppner-ruling-what-the-court
22. https://verdict.justia.com/2026/03/30/the-first-federal-ai-privilege-ruling-gets-the-right-result-for-the-wrong-reasons
23. https://news.bloomberglaw.com/legal-exchange-insights-and-commentary/heppner-shows-attorney-client-privileges-fragility-in-ai-era
24. https://minnlawyer.com/2025/10/21/legal-malpractice-trends-aba-epic-lockton-2020-2023/
25. https://www.tlie.org/resource/scheduling-errors-and-legal-malpractice
26. https://caretlegal.com/blog/malpractice-for-missed-deadlines-a-litigators-constant-fear-how-to-curb-it/
27. https://lawtoolbox.com/deadline-calculator/
28. https://www.aderant.com/solutions-compulaw/
29. https://wsba.org/for-legal-professionals/member-support/practice-management-assistance/guides/document-retention-guide
30. https://www.leanlaw.co/blog/a-guide-to-document-retention-policies-how-long-must-you-keep-closed-client-files/
31. https://www.nhbar.org/file-retention-guidelines/
32. https://www.ncbar.gov/for-lawyers/ethics/adopted-opinions/rpc-209/
33. https://judicature.duke.edu/articles/rule-37e-the-new-law-of-electronic-spoliation/
34. https://judicature.duke.edu/articles/amended-rule-37e-whats-new-and-whats-next-in-spoliation/
35. https://www.everlaw.com/blog/ediscovery-best-practices/guide-to-legal-holds/
36. https://bostonbar.org/journal/the-impact-of-recent-revisions-to-fed-r-civ-p-37e-electronic-spoliation/
37. https://www.calbar.ca.gov/Portals/0/documents/ethics/Opinions/CAL%202015-193%20%5B11-0004%5D%20(06-30-15)%20-%20FINAL.pdf
38. https://www.sfbar.org/blog/electronically-stored-information-and-the-duty-of-competence/
39. https://ailegalauthority.com/ai-unauthorized-practice-of-law/
40. https://www.thomsonreuters.com/en-us/posts/government/ai-impacts-unauthorized-practice-of-law/
41. https://jolt.richmond.edu/is-your-artificial-intelligence-guilty-of-the-unauthorized-practice-of-law/
42. https://www.ftc.gov/news-events/news/press-releases/2024/09/ftc-announces-crackdown-deceptive-ai-claims-schemes
43. https://www.lathropgpm.com/insights/transparency-and-ai-ftc-launches-enforcement-actions-against-businesses-promoting-deceptive-ai-product-claims/
44. https://www.legal.io/articles/5798485/OpenAI-Sued-for-Unauthorized-Practice-of-Law-via-ChatGPT
45. https://www.beneschlaw.com/insight/one-year-in-ftcs-operation-ai-comply-continues-under-new-administration-signaling-enduring-enforcement-focus/
46. https://leg.colorado.gov/bills/sb24-205
47. https://www.lawandtheworkplace.com/2026/04/colorado-takes-a-major-step-towards-rewriting-its-ai-law-as-its-effective-date-approaches/
48. https://www.nortonrosefulbright.com/en-us/knowledge/publications/18733d31/colorado-enacts-revised-ai-law
49. https://www.troutmanprivacy.com/2026/05/colorado-legislature-passes-bill-to-repeal-and-replace-colorado-ai-act/
50. https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB942
51. https://www.pillsburylaw.com/en/news-and-insights/new-california-ai-laws.html
52. https://www.clio.com/blog/solo-small-law-firms-highlights-2025-legal-trends/
53. https://www.clio.com/blog/solo-small-law-firms-2024-legal-trends/
54. https://www.clio.com/resources/legal-trends/benchmarks/
55. https://www.thomsonreuters.com/en-us/posts/wp-content/uploads/sites/20/2025/04/The-AI-driven-future_2025.pdf
56. https://www.thomsonreuters.com/en-us/posts/legal/future-of-professionals-report-analysis-law-firm-economics/
57. https://www.everlaw.com/blog/ai-and-law/lawyers-report-saving-up-to-32-5-working-days-per-year-with-generative-ai/
58. https://www.everlaw.com/blog/case-studies/am-law-100-firm-slashed-doc-review-time-by-two-thirds-with-genai/
59. https://www.embroker.com/blog/solo-law-firm-statistics/
